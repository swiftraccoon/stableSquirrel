#!/usr/bin/env python3
"""
Stress test utility for RdioScanner API ingestion.

Tests concurrent upload capacity, memory usage, and failure modes.
"""

import asyncio
import logging
import random
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import aiohttp

try:
    import psutil  # Optional dependency - install with: uv add psutil
except ImportError:
    psutil = None
import argparse
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class TestConfig:
    """Configuration for stress testing."""
    base_url: str = "http://localhost:8000"
    api_key: str = "test-api-key"
    max_concurrent: int = 50
    total_requests: int = 1000
    ramp_up_time: int = 30  # seconds
    test_duration: int = 300  # seconds
    file_size_range: Tuple[int, int] = (1024, 1024*1024)  # 1KB to 1MB
    systems: List[str] = field(default_factory=lambda: ["100", "200", "300"])
    talkgroups: List[int] = field(default_factory=lambda: list(range(1000, 1010)))


@dataclass
class TestResult:
    """Results from a single API call."""
    success: bool
    response_time: float
    status_code: int
    error_message: Optional[str] = None
    memory_usage_mb: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StressTestReport:
    """Complete stress test results."""
    config: TestConfig
    results: List[TestResult]
    start_time: datetime
    end_time: datetime
    peak_memory_mb: float
    avg_response_time: float
    success_rate: float
    requests_per_second: float
    error_breakdown: Dict[str, int]


class MockAudioGenerator:
    """Generates mock audio files for testing."""

    def __init__(self):
        self.mp3_header = self._create_mp3_header()

    def _create_mp3_header(self) -> bytes:
        """Create a minimal valid MP3 header."""
        # ID3v2 header (10 bytes) + minimal MP3 frame
        id3_header = b'ID3\x03\x00\x00\x00\x00\x00\x00'
        mp3_frame = b'\xff\xfb\x90\x00' + b'\x00' * 100  # Minimal MP3 frame
        return id3_header + mp3_frame

    async def generate_audio_file(self, size_bytes: int) -> bytes:
        """Generate a mock MP3 audio file of specified size."""
        base_content = self.mp3_header

        if size_bytes <= len(base_content):
            return base_content[:size_bytes]

        # Pad with random data to reach desired size
        padding_size = size_bytes - len(base_content)
        padding = bytes([random.randint(0, 255) for _ in range(padding_size)])

        return base_content + padding


class RdioScannerStressTester:
    """Main stress testing class."""

    def __init__(self, config: TestConfig):
        self.config = config
        self.audio_generator = MockAudioGenerator()
        self.session: Optional[aiohttp.ClientSession] = None
        self.process = psutil.Process() if psutil else None
        self.results: List[TestResult] = []
        self.peak_memory = 0.0

    async def __aenter__(self):
        """Async context manager entry."""
        connector = aiohttp.TCPConnector(
            limit=self.config.max_concurrent * 2,
            limit_per_host=self.config.max_concurrent,
            keepalive_timeout=30
        )

        timeout = aiohttp.ClientTimeout(total=60, connect=10)

        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    def _monitor_memory(self):
        """Monitor memory usage during test."""
        if not psutil:
            return None

        try:
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            self.peak_memory = max(self.peak_memory, memory_mb)
            return memory_mb
        except Exception:
            return None

    async def _create_test_request_data(self) -> Tuple[aiohttp.FormData, Dict]:
        """Create test request data with random values."""
        system = random.choice(self.config.systems)
        talkgroup = random.choice(self.config.talkgroups)
        frequency = 460000000 + random.randint(0, 100000)  # 460-460.1 MHz range
        source = random.randint(1000, 9999)

        # Generate audio file
        file_size = random.randint(*self.config.file_size_range)
        audio_content = await self.audio_generator.generate_audio_file(file_size)

        # Create form data
        form_data = aiohttp.FormData()
        form_data.add_field('key', self.config.api_key)
        form_data.add_field('system', system)
        form_data.add_field('dateTime', str(int(time.time())))
        form_data.add_field('frequency', str(frequency))
        form_data.add_field('talkgroup', str(talkgroup))
        form_data.add_field('source', str(source))
        form_data.add_field('systemLabel', f'Test System {system}')
        form_data.add_field('talkgroupLabel', f'Test TG {talkgroup}')

        # Add audio file
        form_data.add_field(
            'audio',
            audio_content,
            filename=f'test_call_{system}_{talkgroup}_{int(time.time())}.mp3',
            content_type='audio/mpeg'
        )

        metadata = {
            'system': system,
            'talkgroup': talkgroup,
            'frequency': frequency,
            'file_size': file_size
        }

        return form_data, metadata

    async def _send_request(self, request_id: int) -> TestResult:
        """Send a single test request."""
        start_time = time.time()

        try:
            form_data, metadata = await self._create_test_request_data()

            # Monitor memory before request
            memory_before = self._monitor_memory()

            if not self.session:
                raise RuntimeError("Session not initialized")

            async with self.session.post(
                f"{self.config.base_url}/api/call-upload",
                data=form_data
            ) as response:
                response_time = time.time() - start_time

                # Try to read response
                try:
                    response_text = await response.text()
                except Exception:
                    response_text = ""

                success = response.status in [200, 201]
                error_msg = None if success else f"HTTP {response.status}: {response_text[:100]}"

                return TestResult(
                    success=success,
                    response_time=response_time,
                    status_code=response.status,
                    error_message=error_msg,
                    memory_usage_mb=memory_before
                )

        except asyncio.TimeoutError:
            return TestResult(
                success=False,
                response_time=time.time() - start_time,
                status_code=0,
                error_message="Request timeout",
                memory_usage_mb=self._monitor_memory()
            )
        except Exception as e:
            return TestResult(
                success=False,
                response_time=time.time() - start_time,
                status_code=0,
                error_message=f"Exception: {str(e)[:100]}",
                memory_usage_mb=self._monitor_memory()
            )

    async def _ramp_up_test(self) -> List[TestResult]:
        """Gradual ramp-up test to find breaking point."""
        logger.info("Starting ramp-up test...")
        results = []

        # Start with low concurrency and gradually increase
        for concurrency in range(1, self.config.max_concurrent + 1, 5):
            logger.info(f"Testing with {concurrency} concurrent requests...")

            # Send batch of concurrent requests
            tasks = []
            for i in range(concurrency):
                task = asyncio.create_task(self._send_request(i))
                tasks.append(task)

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            batch_success_rate = 0
            for result in batch_results:
                if isinstance(result, TestResult):
                    results.append(result)
                    if result.success:
                        batch_success_rate += 1
                else:
                    # Handle exceptions
                    results.append(TestResult(
                        success=False,
                        response_time=0,
                        status_code=0,
                        error_message=f"Task exception: {str(result)[:100]}"
                    ))

            batch_success_rate = batch_success_rate / concurrency if concurrency > 0 else 0
            logger.info(f"Concurrency {concurrency}: {batch_success_rate:.1%} success rate")

            # If success rate drops below 80%, we've found the limit
            if batch_success_rate < 0.8:
                logger.warning(f"Breaking point found at {concurrency} concurrent requests")
                break

            # Small delay between batches
            await asyncio.sleep(1)

        return results

    async def _sustained_load_test(self) -> List[TestResult]:
        """Sustained load test over specified duration."""
        logger.info(f"Starting sustained load test for {self.config.test_duration} seconds...")

        results = []
        start_time = time.time()
        end_time = start_time + self.config.test_duration

        # Use a semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self.config.max_concurrent)

        async def limited_request(request_id: int) -> TestResult:
            async with semaphore:
                return await self._send_request(request_id)

        request_id = 0

        while time.time() < end_time:
            # Calculate how many requests to send this second
            requests_this_batch = min(10, self.config.max_concurrent // 5)

            # Create tasks for this batch
            tasks = []
            for _ in range(requests_this_batch):
                task = asyncio.create_task(limited_request(request_id))
                tasks.append(task)
                request_id += 1

            # Wait for batch to complete or timeout
            try:
                batch_results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=10.0
                )

                for result in batch_results:
                    if isinstance(result, TestResult):
                        results.append(result)
                    else:
                        results.append(TestResult(
                            success=False,
                            response_time=0,
                            status_code=0,
                            error_message=f"Batch timeout: {str(result)[:100]}"
                        ))

            except asyncio.TimeoutError:
                logger.warning("Batch timeout occurred")
                for task in tasks:
                    task.cancel()

            # Brief pause between batches
            await asyncio.sleep(0.1)

        logger.info(f"Sustained load test completed. Sent {len(results)} requests.")
        return results

    async def run_stress_test(self) -> StressTestReport:
        """Run complete stress test suite."""
        logger.info("Starting RdioScanner API stress test...")
        start_time = datetime.now()

        # Run ramp-up test first
        ramp_results = await self._ramp_up_test()

        # Small break between tests
        await asyncio.sleep(5)

        # Run sustained load test
        sustained_results = await self._sustained_load_test()

        # Combine all results
        all_results = ramp_results + sustained_results
        self.results = all_results

        end_time = datetime.now()

        # Generate report
        return self._generate_report(start_time, end_time)

    def _generate_report(self, start_time: datetime, end_time: datetime) -> StressTestReport:
        """Generate comprehensive test report."""
        if not self.results:
            raise ValueError("No test results to generate report from")

        # Calculate statistics
        successful_results = [r for r in self.results if r.success]
        success_rate = len(successful_results) / len(self.results)

        response_times = [r.response_time for r in successful_results]
        avg_response_time = statistics.mean(response_times) if response_times else 0

        total_duration = (end_time - start_time).total_seconds()
        requests_per_second = len(self.results) / total_duration if total_duration > 0 else 0

        # Error breakdown
        error_breakdown = {}
        for result in self.results:
            if not result.success:
                error_key = f"HTTP {result.status_code}" if result.status_code > 0 else "Connection Error"
                error_breakdown[error_key] = error_breakdown.get(error_key, 0) + 1

        return StressTestReport(
            config=self.config,
            results=self.results,
            start_time=start_time,
            end_time=end_time,
            peak_memory_mb=self.peak_memory,
            avg_response_time=avg_response_time,
            success_rate=success_rate,
            requests_per_second=requests_per_second,
            error_breakdown=error_breakdown
        )


def print_report(report: StressTestReport):
    """Print formatted test report."""
    print("\n" + "="*80)
    print("           RDIOSCANNER API STRESS TEST REPORT")
    print("="*80)

    duration = (report.end_time - report.start_time).total_seconds()

    print("\n📊 TEST SUMMARY")
    print(f"   Duration: {duration:.1f} seconds")
    print(f"   Total Requests: {len(report.results)}")
    print(f"   Successful: {sum(1 for r in report.results if r.success)}")
    print(f"   Failed: {sum(1 for r in report.results if not r.success)}")
    print(f"   Success Rate: {report.success_rate:.1%}")
    print(f"   Requests/Second: {report.requests_per_second:.1f}")

    print("\n⚡ PERFORMANCE")
    print(f"   Average Response Time: {report.avg_response_time:.3f}s")

    successful_times = [r.response_time for r in report.results if r.success]
    if successful_times:
        print(f"   Median Response Time: {statistics.median(successful_times):.3f}s")
        print(f"   95th Percentile: {statistics.quantiles(successful_times, n=20)[18]:.3f}s")
        print(f"   Max Response Time: {max(successful_times):.3f}s")

    print("\n💾 MEMORY USAGE")
    print(f"   Peak Memory: {report.peak_memory_mb:.1f} MB")

    if report.error_breakdown:
        print("\n❌ ERROR BREAKDOWN")
        for error_type, count in sorted(report.error_breakdown.items()):
            percentage = (count / len(report.results)) * 100
            print(f"   {error_type}: {count} ({percentage:.1f}%)")

    print("\n🎯 LOAD TEST CONFIGURATION")
    print(f"   Max Concurrent: {report.config.max_concurrent}")
    print(f"   Base URL: {report.config.base_url}")
    print(f"   File Size Range: {report.config.file_size_range[0]/1024:.0f}KB - "
          f"{report.config.file_size_range[1]/1024:.0f}KB")

    print("\n" + "="*80)


async def main():
    """Main stress test execution."""
    parser = argparse.ArgumentParser(description="RdioScanner API Stress Test")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL for API")
    parser.add_argument("--api-key", default="test-api-key", help="API key for authentication")
    parser.add_argument("--max-concurrent", type=int, default=50, help="Maximum concurrent requests")
    parser.add_argument("--duration", type=int, default=120, help="Test duration in seconds")
    parser.add_argument("--total-requests", type=int, default=1000, help="Total requests to send")

    args = parser.parse_args()

    config = TestConfig(
        base_url=args.url,
        api_key=args.api_key,
        max_concurrent=args.max_concurrent,
        test_duration=args.duration,
        total_requests=args.total_requests
    )

    try:
        async with RdioScannerStressTester(config) as tester:
            report = await tester.run_stress_test()
            print_report(report)

            # Save detailed report to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = f"stress_test_report_{timestamp}.txt"

            with open(report_file, 'w') as f:
                f.write("RdioScanner API Stress Test Report\n")
                f.write(f"Generated: {datetime.now()}\n\n")
                f.write(f"Success Rate: {report.success_rate:.1%}\n")
                f.write(f"Average Response Time: {report.avg_response_time:.3f}s\n")
                f.write(f"Peak Memory: {report.peak_memory_mb:.1f} MB\n")
                f.write(f"Requests/Second: {report.requests_per_second:.1f}\n\n")

                f.write("Individual Results:\n")
                for i, result in enumerate(report.results):
                    f.write(f"{i+1}: {'✓' if result.success else '✗'} "
                           f"{result.response_time:.3f}s "
                           f"HTTP {result.status_code} "
                           f"{result.error_message or ''}\n")

            print(f"\n📄 Detailed report saved to: {report_file}")

            # Exit with appropriate code
            if report.success_rate < 0.95:
                print("\n⚠️  WARNING: Success rate below 95% - API may have issues under load")
                sys.exit(1)
            else:
                print("\n✅ API performed well under stress test conditions")
                sys.exit(0)

    except KeyboardInterrupt:
        print("\n🛑 Stress test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Stress test failed with error: {e}")
        logger.exception("Stress test exception")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
