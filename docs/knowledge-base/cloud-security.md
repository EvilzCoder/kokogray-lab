---
title: Cloud security
description: Start with identities, permissions, and the boundaries between services.
---

# Cloud security

Cloud systems are collections of identities acting on resources. Before examining individual settings, map who can do what, to which resource, and under which conditions.

## Map the trust boundaries

List the components in the permitted lab environment and draw the requests between them. A useful map includes the public entry point, the runtime identity, the data store, and any external dependencies.

| Component | Questions to ask |
| --- | --- |
| Entry point | Who can reach it? Where is authentication enforced? |
| Runtime identity | Which principal does the application use? |
| Data store | Which identities can read, write, or administer it? |
| Automation | What can build and deployment identities access? |

## Identity and permissions

### Distinguish identity from authority

Authentication establishes an identity. Authorization decides whether that identity may perform a specific action. Having a valid credential does not mean every action should be allowed.

Check whether permissions are scoped to the resources the workload actually needs. Pay attention to inherited permissions and policy conditions rather than reading one policy in isolation.

### Prefer short-lived credentials

Use workload identity or other short-lived credentials where possible. Avoid putting long-lived keys in source code, images, notebook output, or published writeups.

!!! warning "Publishing checklist"
    Screenshots and logs can contain usable tokens even when the main password field is hidden. Review URLs, headers, environment output, and terminal history before sharing.

## Storage and data exposure

Evaluate both the resource policy and the identity policy. Check whether a resource is intended to be public, whether listing differs from reading an object, and whether access paths bypass the expected application controls.

For your own lab, use synthetic data. You should not need real customer records to verify an access-control boundary.

## Logs and evidence

Record the principal, action, resource, timestamp, and observed outcome for each authorized check. Keep only the evidence needed to support the conclusion.

```json
{
  "environment": "local-lab",
  "principal": "example-read-only-role",
  "action": "read-example-object",
  "expected": "allowed",
  "observed": "record-after-testing"
}
```

This is an example record format, not output from an actual test.

## Defensive review

- Remove permissions the workload does not need.
- Keep administrative identities separate from application identities.
- Apply access checks at the resource boundary, not only in the UI.
- Enable the relevant audit logs before you need them.
- Test the denied path as well as the successful path.

## References

- [AWS IAM security best practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [Google Cloud IAM overview](https://cloud.google.com/iam/docs/overview)
- [Microsoft Entra fundamentals](https://learn.microsoft.com/en-us/entra/fundamentals/whatis)
