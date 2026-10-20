# RESQ-AI Docker and Frontend 504 Report

**Prepared:** 2026-10-20  
**Scope:** Summary of blockers and observations from the acceptance work already
performed. No new commands, services, or tests were run to prepare this report.

## Summary

The Docker problem observed earlier was that Docker Desktop's Linux engine was
not reachable. This prevented starting a PostgreSQL/PostGIS container at that
time. Later in the acceptance work, Docker became available: a disposable
PostGIS container started successfully, database migrations completed, and
database-backed checks ran against it. So the evidence does **not** show that
Docker is still unable to open; it shows an earlier Docker-engine availability
problem that was subsequently resolved.

The available acceptance evidence does **not** confirm that the frontend
actually received an HTTP 504. The prior database-unavailable run recorded
HTTP 500 for data endpoints and HTTP 503 for health. After PostGIS was started,
the checked endpoints returned HTTP 200. A browser client was not connected,
so a 504 in the browser/network panel could not be independently inspected.
The precise cause of the reported 504 therefore remains unverified.

## Docker: what happened and what is established

| Item | Finding |
|---|---|
| Earlier failure | Docker was installed, but the Docker Desktop Linux engine could not be reached. A PostGIS container could not be started in that attempt. |
| Later result | Docker successfully started the isolated `resq-ai-acceptance-postgis-20261020` container, mapped to port 55432. Alembic reached `20261010_0003 (head)`. |
| Database evidence | The API reported the database connected; a synthetic event persisted, and a nearby-resource PostGIS query returned a resource distance of 216.93 m. |
| Current conclusion | The original obstacle was Docker-engine availability at that time, not a demonstrated defect in the application. The later successful container run shows the environment recovered. The temporary test container was stopped after validation. |

### Docker cause: known versus not established

The directly observed cause was that the Docker Desktop engine was unavailable
to the Docker CLI. The checks did not establish why the engine was unavailable.
Possible environmental explanations include Docker Desktop not yet running,
its Linux engine still starting or stopped, or Docker Desktop configured for a
different container mode. Those are possibilities, not confirmed diagnoses.
No report evidence points to the RESQ-AI code preventing Docker from opening.

## Frontend HTTP 504: what it means and what evidence exists

The React development server is configured to proxy API requests to
`http://localhost:8000`. An HTTP **504 Gateway Timeout** normally means that
the proxy/gateway did not receive a timely response from its upstream server.
It is different from an application response such as HTTP 500 or 503.

| Evidence or explanation | Status |
|---|---|
| Frontend proxy target is `http://localhost:8000`. | Verified in the frontend package configuration and development-server startup logs. |
| The earlier database-outage acceptance run saw data API HTTP 500 and health HTTP 503. | Verified. These statuses do not prove a 504 occurred. |
| After the isolated database was running, the checked health, dashboard, events, incidents, resources, infrastructure, and Copilot tools endpoints returned HTTP 200. | Verified for those requests. |
| A 504 was captured from the browser, frontend proxy, or another gateway. | Not verified; no connected browser client or corresponding captured response was available. |
| The root cause of the reported 504. | Undetermined from the available evidence. |

If the reported 504 is reproducible, common causes to investigate are:

1. **The API is not listening or is unreachable from the frontend proxy.** A
   wrong host/port, stopped backend, or container-network address mismatch can
   leave the proxy waiting for its upstream.
2. **The API is waiting on a dependency.** Database connection timeouts,
   unavailable model servers, external feeds, or long AI inference can delay a
   request beyond a proxy timeout. The earlier database outage did produce
   failed API requests, but the recorded responses were 500/503—not a
   confirmed 504.
3. **The request takes longer than the proxy's timeout.** Heavy analysis,
   model loading/download, or a slow external service can cause this. Model
   weights needed for event analysis/embedding were not present locally, but
   the acceptance work did not establish that this produced a frontend 504.
4. **The 504 comes from a different gateway.** If the app is being accessed
   through a hosting proxy, tunnel, load balancer, or another network layer,
   that layer may have its own upstream address and timeout independent of
   the local React development proxy.

These are diagnostic possibilities, not conclusions about the specific 504.
To identify its actual source, the response status and URL from the browser's
Network panel need to be correlated with the frontend proxy log and the
backend log at the same time. The request should also be checked directly
against the configured backend to determine whether the delay is in the API
or in the proxy path. That evidence was not collected in the prior run.

## Other remaining acceptance blockers

These affect demonstration readiness but have not been proven to cause the
reported 504:

- The configured local Ollama model produced text but did not emit the
  structured tool calls required for grounded Copilot answers. The backend
  now fails closed rather than presenting unsupported text as grounded.
- Event-analysis and embedding model weights were unavailable locally, so the
  event-to-incident workflow was not completed.
- Consequently, investigation/evidence, risk and impact, optimization, and
  human review were not verified end to end.
- A browser client was unavailable, so page-specific rendering, JavaScript
  errors, visible frontend error states, and live map rendering were not
  independently checked.

## Conclusion

Docker was initially blocked because its Linux engine was unreachable, but a
later isolated PostGIS startup and successful database checks show that this
blocker was resolved during the acceptance work. The cause of the reported
frontend 504 cannot be stated with confidence: no 504 response was captured in
the available evidence. Earlier observed failures were database-related 500
and 503 responses; later checked API requests returned 200 with PostGIS
available. The application is still not accepted for a complete
data-backed demonstration because the AI-driven workflow and browser
acceptance remain incomplete.
