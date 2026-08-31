# Large Inbox Benchmark

Synthetic benchmark for proving MailMind behavior on a large inbox without exposing private Gmail data.

| Metric | Value |
| --- | ---: |
| Total emails | 10000 |
| Classified emails | 10000 |
| Spam-risk emails | 1000 |
| Unread emails | 3637 |
| Cleanup candidates | 6000 |
| Search index warmup latency | 15742.635 ms |
| Inbox health latency | 971.816 ms |
| Cleanup preview latency | 850.049 ms |
| Avg search latency | 837.061 ms |
| P95 search latency | 1182.441 ms |

## Search Latency

| Query | Mode | Latency | Results | Top Subject |
| --- | --- | ---: | ---: | --- |
| interview schedule | keyword | 888.759 ms | 10 | Backend Engineer interview schedule #1 / 2026-01 |
| interview schedule | vector | 846.561 ms | 10 | Backend Engineer interview schedule #2901 / 2026-09 |
| interview schedule | hybrid | 752.932 ms | 10 | Backend Engineer interview schedule #191 / 2026-11 |
| electricity bill | keyword | 829.015 ms | 10 | Electricity bill invoice is ready #3 / 2026-03 |
| electricity bill | vector | 658.537 ms | 10 | Electricity bill invoice is ready #3133 / 2026-01 |
| electricity bill | hybrid | 667.22 ms | 10 | Electricity bill invoice is ready #73 / 2026-01 |
| discount coupon | keyword | 782.955 ms | 10 | Limited time sale and discount coupon #2 / 2026-02 |
| discount coupon | vector | 991.877 ms | 10 | Electricity bill invoice is ready #7413 / 2026-09 |
| discount coupon | hybrid | 1182.441 ms | 10 | Limited time sale and discount coupon #12 / 2026-12 |
| credit card statement | keyword | 823.262 ms | 10 | Credit card statement generated #4 / 2026-04 |
| credit card statement | vector | 722.55 ms | 10 | Credit card statement generated #8994 / 2026-06 |
| credit card statement | hybrid | 822.323 ms | 10 | Credit card statement generated #244 / 2026-04 |
| cash reward verify account | keyword | 958.397 ms | 10 | You have won a cash reward #9 / 2026-09 |
| cash reward verify account | vector | 863.057 ms | 10 | You have won a cash reward #8889 / 2026-09 |
| cash reward verify account | hybrid | 766.033 ms | 10 | You have won a cash reward #9 / 2026-09 |
