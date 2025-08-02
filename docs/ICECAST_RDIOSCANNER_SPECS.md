# Icecast 2.4+ Streaming and RdioScanner Calls API

This document summarizes the connection and payload specifications used by **sdrtrunk**
for Icecast 2.4+ streaming as well as the RdioScanner calls upload API.  It is
intended to help developers integrate these features into a custom recording and
transcription system.

## Icecast 2.4+ (HTTP) Streaming

`sdrtrunk` implements Icecast 2.4+ support with the `IcecastHTTPAudioBroadcaster`
class.  This broadcaster uses an HTTP/1.1 socket connection and sends a PUT
request when opening the stream.  Relevant comments describing the
implementation can be seen here:

```
    /**
     * Creates an Icecast 2.4.x compatible broadcaster using HTTP 1.1 protocol. This broadcaster is
     * compatible with Icecast version 2.4.x and newer versions of the server software.
     *
     * Note: use @see IcecastTCPAudioBroadcaster for Icecast version 2.3.x and older.
     */
```
【F:sdrtrunk/src/main/java/io/github/dsheirer/audio/broadcast/icecast/IcecastHTTPAudioBroadcaster.java†L60-L72】

When a session is opened, the broadcaster sends a PUT request to the mount point
with a collection of Icecast specific headers:

```
HttpRequestImpl request = new HttpRequestImpl(HttpVersion.HTTP_1_1, HttpMethod.PUT,
    getConfiguration().getMountPoint(), "", getHTTPHeaders());
```
【F:sdrtrunk/src/main/java/io/github/dsheirer/audio/broadcast/icecast/IcecastHTTPAudioBroadcaster.java†L234-L236】

The headers are derived from the configuration and include fields such as
`Content-Type`, `Authorization`, `ice-audio-info` and `icy-metaint`.  The header
names are enumerated in `IcecastHeader`:

```
ACCEPT("Accept"),
AUDIO_INFO("ice-audio-info"),
AUTHORIZATION("Authorization"),
BITRATE("ice-bitrate"),
CONTENT_TYPE("Content-Type"),
DESCRIPTION("ice-description"),
EXPECT("Expect"),
GENRE("ice-genre"),
HOST("Host"),
NAME("ice-name"),
PUBLIC("ice-public"),
URL("ice-url"),
USER_AGENT("User-Agent"),
METAINT("icy-metaint"),
```
【F:sdrtrunk/src/main/java/io/github/dsheirer/audio/broadcast/icecast/IcecastHeader.java†L23-L40】

`IcecastHTTPConfiguration` extends `IcecastConfiguration` and stores common
stream parameters such as host, port, mount point, user credentials, bit rate,
channels, sample rate and whether metadata is sent inline.  These parameters are
validated so that a proper Icecast connection can be established.

Icecast sends status responses that are parsed by `IcecastHTTPIOHandler`.  On a
successful handshake the broadcaster transitions to `CONNECTED`; authentication
errors result in `INVALID_CREDENTIALS` or `CONFIGURATION_ERROR` states.
`IcecastHTTPIOHandler` also handles the special case where Icecast 2.4.2 responds
with a minimal `HTTP/1.0 200 OK` message without headers, as noted in the code
comments.

## RdioScanner Calls API

The RdioScanner API allows pushing completed calls to a remote server via a
multipart HTTP POST.  The implementation is in `RdioScannerBroadcaster`.
Initialization of the HTTP client is shown below:

```
private HttpClient mHttpClient = HttpClient.newBuilder()
    .version(HttpClient.Version.HTTP_2)
    .followRedirects(HttpClient.Redirect.NORMAL)
    .connectTimeout(Duration.ofSeconds(20))
    .build();
```
【F:sdrtrunk/src/main/java/io/github/dsheirer/audio/broadcast/rdioscanner/RdioScannerBroadcaster.java†L73-L78】

When a call is processed, `RdioScannerBroadcaster` constructs a multipart form
containing the audio file and metadata fields.  The builder usage shows the full
set of parts that are sent:

```
RdioScannerBuilder bodyBuilder = new RdioScannerBuilder();
    bodyBuilder.addPart(FormField.KEY, getBroadcastConfiguration().getApiKey())
        .addPart(FormField.SYSTEM, getBroadcastConfiguration().getSystemID())
        .addAudioName(audioName)
        .addFile(audioBytes)
        .addPart(FormField.DATE_TIME, timestampSeconds)
        .addPart(FormField.TALKGROUP_ID, talkgroup)
        .addPart(FormField.SOURCE, radioId)
        .addPart(FormField.FREQUENCY, frequency)
        .addPart(FormField.TALKER_ALIAS, talkerAlias)
        .addPart(FormField.TALKGROUP_LABEL, talkgroupLabel)
        .addPart(FormField.TALKGROUP_GROUP, talkgroupGroup)
        .addPart(FormField.SYSTEM_LABEL, systemLabel)
        .addPart(FormField.PATCHES, patches);
```
【F:sdrtrunk/src/main/java/io/github/dsheirer/audio/broadcast/rdioscanner/RdioScannerBroadcaster.java†L254-L272】

The available form fields are enumerated in `FormField`:

```
AUDIO("audio"),
AUDIO_NAME("audioName"),
AUDIO_TYPE("audioType"),
DATE_TIME("dateTime"),
FREQUENCIES("frequencies"),
FREQUENCY("frequency"),
KEY("key"),
PATCHES("patches"),
SOURCE("source"),
SOURCES("sources"),
SYSTEM("system"),
SYSTEM_LABEL("systemLabel"),
TALKER_ALIAS("talkerAlias"),
TALKGROUP_ID("talkgroup"),
TALKGROUP_GROUP("talkgroupGroup"),
TALKGROUP_LABEL("talkgroupLabel"),
TALKGROUP_TAG("talkgroupTag"),
TEST("test");
```
【F:sdrtrunk/src/main/java/io/github/dsheirer/audio/broadcast/rdioscanner/FormField.java†L25-L48】

`RdioScannerConfiguration` stores the system ID, API key and host URL for the
upload endpoint.  If no host is provided it defaults to `http://localhost`:

```
if(mHost.getValue() == null || mHost.getValue().isEmpty())
{
    mHost.set("http://localhost");
}
```
【F:sdrtrunk/src/main/java/io/github/dsheirer/audio/broadcast/rdioscanner/RdioScannerConfiguration.java†L60-L67】

To verify connectivity, the broadcaster issues a test request containing the
`KEY`, `SYSTEM` and `TEST` fields.  The helper method reports the response and
status code:

```
RdioScannerBuilder bodyBuilder = new RdioScannerBuilder();
bodyBuilder.addPart(FormField.KEY, configuration.getApiKey())
    .addPart(FormField.SYSTEM, configuration.getSystemID())
    .addPart(FormField.TEST, 1);

HttpRequest request = HttpRequest.newBuilder()
    .uri(URI.create(configuration.getHost()))
    .header(HttpHeaders.CONTENT_TYPE, MULTIPART_FORM_DATA + "; boundary=" + bodyBuilder.getBoundary())
    .header(HttpHeaders.USER_AGENT, "sdrtrunk")
    .header(HttpHeaders.ACCEPT, "*/*")
    .POST(bodyBuilder.build())
    .build();
```
【F:sdrtrunk/src/main/java/io/github/dsheirer/audio/broadcast/rdioscanner/RdioScannerBroadcaster.java†L584-L603】

### Multipart Formatting

`RdioScannerBuilder` creates the multipart body with a static boundary string:

```
private static final String BOUNDARY = "--sdrtrunk-sdrtrunk-sdrtrunk";
```
【F:sdrtrunk/src/main/java/io/github/dsheirer/audio/broadcast/rdioscanner/RdioScannerBuilder.java†L34-L35】

Each field is added as `Content-Disposition: form-data` parts, followed by the
optional audio file.  The boundary is appended at the end of the body before the
request is sent.

## Summary

- **Icecast 2.4+** – Streams audio via HTTP/1.1 using a PUT request.  Headers such
  as `ice-audio-info`, `ice-name`, `ice-url`, `ice-genre` and `icy-metaint` are
  sent to describe the stream and provide credentials.  Inline metadata can be
  enabled by setting the `icy-metaint` header with the interval in bytes.
- **RdioScanner Calls API** – Uploads completed calls as multipart form data.
  Required fields include the API key and system ID.  Additional metadata (talkgroup,
  source radio ID, frequency, labels, etc.) can be supplied for each call.  The
  API provides a test mode using the `test` field to confirm connectivity.

These code references provide the necessary structure for implementing both
protocols in a custom recording and transcription workflow.
