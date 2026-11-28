# Review of the LAN/Gossip audit and synthesis evidence

**Hold integration** at candidate `56c2298c4ae223040932fcef01cab2edae82414c`.
This review concerns the candidate and the reports, not live operations.

1. **Verifier contract.** In `AuthorityService._check_auth`, only the literal
   result `False` is rejected. An unintended `None` result is accepted.
   Unexpected verifier exceptions are converted into client-visible messages
   containing exception text. Define explicit success, deny unexpected results,
   and test that verifier failures disclose no internal details or write state.
2. **Implementation is not qualification.** The candidate adds the service and
   lease operations, but the reported 13 Windows passes and 24 skips do not
   establish native POSIX behavior. Return exact-candidate macOS results for
   store migration, preservation of legacy terminal states, stale-handle
   rejection, authorization, and clock sampling under the write lock.
   Align the plan with the actual interface: it specifies no free-text fail
   parameter, while the candidate accepts a detail argument and ignores it.
3. **Lane 5 remains open.** Rule-level examples and a reported 199 passing tests
   do not establish the labels of all 55 historical firings. Supply sanitized
   per-event label evidence, fixture provenance, and an independently repeatable
   native default-directory TLS control.
4. **Transport is separate.** The consolidated report and the local ZIP agree,
   but Gossip row 1297 names a different ZIP digest. Compare the receiver's
   decoded bytes and [member hashes](2026-11-28-synthesis-manifest.md) before
   calling the copies identical. A portal acknowledgement is not a test receipt
   or a reviewer's acceptance. No raw bundle replay is needed for this check.
