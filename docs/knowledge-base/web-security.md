---
title: Web security
description: Understand requests, sessions, and server-side decisions before testing a hypothesis.
---

# Web security

A browser shows the interface, but the server must enforce the rules. In a local or authorized challenge environment, start by understanding a normal request and the identity attached to it.

## Understand the request

Record the method, path, parameters, body format, session mechanism, and expected response. Look for the difference between a value controlled by a user and a decision made by the server.

| Layer | What to understand |
| --- | --- |
| Transport | HTTPS, redirects, and proxy behavior |
| Session | How the application recognizes a user |
| Authorization | Where access to an action or object is checked |
| Input handling | How data is parsed, validated, and encoded |
| Response | What is returned and which caches can store it |

## Authentication and authorization

### Test the intended boundary

For an application you own, a useful regression test checks that one test account cannot access another test account's private fixture. Use synthetic users and data, not unrelated real accounts.

### Check server-side enforcement

A hidden button is not an access-control boundary. The server should validate the session, requested operation, and resource ownership for every protected request.

!!! note "Keep observations precise"
    A different response status is an observation, not a complete finding. Explain what data or action became available and why the result violates the intended rules.

## Input and output

Treat untrusted data according to the context in which it is used. Database queries, HTML, URLs, and operating-system arguments each need their own safe handling.

Prefer established framework features: parameterized queries, contextual output encoding, allowlisted validation, and safe file APIs.

## Session handling

Review cookie attributes, session expiry, logout behavior, and changes in privilege. A local test should confirm both that valid sessions work and that expired or revoked sessions fail.

```text
Given: a synthetic user signs in to the local test app
When: the user signs out
Then: the previous session cannot access protected fixtures
```

## Document the lesson

Show the expected behavior, the actual behavior, the minimal evidence, and the server-side fix. Explain any assumptions and limitations so a reader does not mistake a lab observation for a claim about a production system.

## References

- [OWASP Web Security Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)
- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/)
- [MDN HTTP overview](https://developer.mozilla.org/en-US/docs/Web/HTTP/Overview)
