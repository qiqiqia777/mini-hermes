# Issue 01 live verification — 2026-10-22

The CRM workspace now reads real Odoo opportunities. The user confirmed manual
QA on 2026-10-22. Issue 01 remains open for the repository's release gates.
No push was made.

## Live environment

- Odoo Server 19.0-20261015, PostgreSQL 16.15; isolated `crm_demo` database.
- Odoo: http://192.168.106.100:8069; workspace: http://127.0.0.1:7777/#crm.
- Dedicated API user has a custom reader group only. ACL checks for crm.lead,
  res.partner and crm.stage allow read and deny create/write/unlink. Record rules
  restrict the reader to the demo fixtures and their related records.
- Credentials are in private backend configuration, excluded from Git and UI.
  The demo API key expires after 30 days (2026-11-21).
- Original containers remained stopped. Existing data and untracked files were
  preserved. No global Docker/proxy configuration or object-store repair occurred.

## Bug found against real Odoo

In Odoo 19, crm.lead.commercial_partner_id is false when partner_id is already
the company. The previous mapping incorrectly displayed "No customer linked".
The adapter now also reads partner_id and uses it when commercial_partner_id is
absent, while retaining the company ahead of a contact when both are available.

Red: the new direct-company regression test returned None instead of the company
name (1 failed, 1 passed). Green: focused CRM and static tests 15 passed.

## Evidence

| Internal opportunity ID | Scenario | Displayed customer | Stage |
| --- | --- | --- | --- |
| 1 | Direct company: 华东客户扫码枪急单跟进 | 华东办公设备集团 | 需求确认 |
| 2 | Company contact: 华东分店补货意向 | 华东办公设备集团 | 需求确认 |
| 3 | No customer: 未关联客户的演示商机 | No customer linked | 需求确认 |

Real JSON-2 reads and the local HTTP endpoint returned these records. Browser
checks covered selection/details, contact-to-company display, missing customer,
Reload and full-page refresh clearing selection. Stopping only the demo Odoo
container produced the connection-error state; starting the same container and
clicking Retry restored the real list. Browser logs contained no warnings/errors.
These are automated browser checks, not the user's manual QA.

After these checks, all three crm.lead.write_date values still matched the initial
database evidence (`2026-10-22 14:35:34.617306` UTC); CRM activity count was zero.
The integration performs only search_read; no model calls or business mutations.

Independent review of ce25e54 and a follow-up review of this fix found no confirmed
P1/P2 defects. The reviewer independently reran the 15 focused tests.

## Validation and remaining gates

- `.venv/Scripts/python.exe -X utf8 -m pytest -q evals/deterministic/test_crm_read.py evals/deterministic/test_static_assets.py`: 15 passed.
- Ruff on the new CRM module: passed. All static JavaScript `node --check`: passed.
- With `PYTHONUTF8=1`, `python -m minihermes.ops.release_gate`: 197 passed,
  11 skipped, 4 failed; judge not run. Without inherited UTF-8 mode the gate's
  subprocess output decoding also fails on Windows.
- Existing failures: three test_coding_eval cases use a missing `/usr/bin/true`
  executable on Windows; the old `walku minihermes` wake-word fixture scores
  0.595 against a 0.7 threshold. These files were not changed for this CRM slice.
- Full repository Ruff: 396 findings; no broad automatic fixes applied.
- User manual QA: accepted on 2026-10-22. After receiving the manual verification
  checklist, the user explicitly replied "人工验收通过". This records the user's
  acceptance without claiming any previously unrun checks were executed.
- Real empty-result browser state: not run; mocked empty-result coverage exists.
- Publish: blocked by the existing gates; Issue 02 has not started.
