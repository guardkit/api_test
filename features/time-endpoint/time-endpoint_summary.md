# Server Time Endpoint — the one-minute read

**What it is:** `GET /time` returns the server's current clock as JSON with
exactly two fields — `"time"` (the current UTC moment, ISO-8601, second
precision, trailing `Z`) and `"service"` (`"api_test"`).

**The four scenarios, one sentence each:**

1. **Reading the time** — a GET returns 200 with exactly those two fields and
   a current, well-formed UTC timestamp.
2. **Freshness** — two requests a second apart return two different, ordered
   timestamps (a hardcoded value cannot pass).
3. **Write methods rejected** — POST, PUT and DELETE all get 405.
4. **Database down** — the endpoint keeps answering 200, because it genuinely
   has no database dependency (its dependency-down story is proven
   unaffectedness).

**The three assumptions awaiting your word:** the exact timestamp shape
(`...T12:34:56Z` — no milliseconds), no caching (computed fresh per request),
and database-down = unaffected-200 rather than 503.

**Why this feature for this sit:** it is deliberately thin (the /version
weight class), it ships for real what the morning's revival proved on
throwaway branches, and it carries the sit's two payloads: the first
anti-cheat `conformance:` block whose receipt will survive (durable receipts
are live now), and the first real unattended-profile build (30-minute cap,
2 review cycles).
