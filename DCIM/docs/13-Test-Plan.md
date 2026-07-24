---
title: Testing Strategy Specification
project: RackDCIM Pro
version: 1.3.0
status: Active
author: Enzo
date: 2026-07-22
last_code_sync: 2026-07-22
category: Testing
---

# Testing Strategy Specification

> Pytest-based test pyramid — unit + integration

---

## Revision History

| Version | Date | Author | Description |
| ------- | ---- | ------ | ----------- |
| 1.3.0 | 2026-07-22 | Enzo | Test inventory, CI matrix, coverage roadmap |

---

## 1. Testing Overview

| Principle | Application |
| --------- | ----------- |
| Test early | Tests alongside features |
| Automation first | Pytest, no manual regression for core flows |
| Risk-based | P0: auth, mount, import |
| CI gate | Unit tests block merge today |

Config: `pytest.ini` at repo root (`pythonpath=backend`).

---

## 2. Quality Targets

| Metric | Target | Current |
| ------ | ------ | ------- |
| Line coverage | ≥90% | 📋 Low |
| Core module coverage | ≥95% | 📋 |
| CI automation | 100% unit pass | ✅ 2 files |
| Integration in CI | Required | ❌ |
| E2E (Playwright) | Critical paths | ❌ |
| P0 defect escape | 0 | 🚧 manual |

---

## 3. Test Pyramid

```text
                    ┌─────────────┐
                    │  E2E / UI   │  📋 Planned
                   ┌┴─────────────┴┐
                   │  Integration  │  ✅ 4 files, not in CI
                  ┌┴───────────────┴┐
                  │   Unit Tests    │  ✅ 2 files, in CI
                  └─────────────────┘
```

---

## 4. Test Inventory

### 4.1 Unit Tests (`tests/unit/`)

| File | Scope | CI |
| ---- | ----- | -- |
| test_health.py | GET /health, GET /api/v1/health | ✅ |
| test_rack_code_prefix.py | expand_row_prefixes, generate_slot_codes | ✅ |

### 4.2 Integration Tests (`tests/integration/`)

| File | Scope | CI |
| ---- | ----- | -- |
| test_auth_datacenter.py | Login, profile, datacenter CRUD, auth guard | ❌ local |
| test_rack.py | Building/floor/room setup, rack CRUD, layout | ❌ local |
| test_device_layout.py | Mount, SVG, dashboard, layout conflict | ❌ local |
| test_export_users.py | Excel import/export/PDF, user/role CRUD | ❌ local |

Fixtures: `tests/conftest.py` — async client, test DB session.

---

## 5. Running Tests

```bash
# All unit (CI equivalent)
cd backend && pytest ../tests/unit -v

# All integration
cd backend && pytest ../tests/integration -v

# Single file
cd backend && pytest ../tests/integration/test_rack.py -v

# With coverage (recommended locally)
cd backend && pytest ../tests --cov=app --cov-report=term-missing
```

---

## 6. Test Cases by Module

### 6.1 Auth & RBAC

| Case | Expected |
| ---- | -------- |
| Login valid credentials | 200 + tokens |
| Login invalid | 401 |
| Access without token | 401 |
| Access without permission | 403 |
| Cannot delete admin user | 403/422 |
| Cannot strip admin role permissions | 403 |

### 6.2 Infrastructure

| Case | Expected |
| ---- | -------- |
| Quick create room | Building + 1F + slot_codes |
| Shrink layout below racks | 10004 error |
| Duplicate slot code | 10004 error |

### 6.3 Rack & Layout

| Case | Expected |
| ---- | -------- |
| Create rack on occupied slot | 10002 |
| Mount 4U at U40 on 42U rack | OK |
| Mount overlapping U | 10004 |
| Unmount frees positions | OK |
| GET rack SVG | 200 + SVG content |

### 6.4 Device Import/Export

| Case | Expected |
| ---- | -------- |
| Download template | xlsx file |
| Import valid rows | created count |
| Import duplicate SN | failed + errors |
| Export xlsx/pdf | file download |

### 6.5 Gaps (Tests Needed)

| Module | Priority |
| ------ | -------- |
| IP addresses (batch, allocate) | P0 |
| Device contracts (import, bind) | P1 |
| Rack place-batch | P1 |
| Audit log API | P2 |
| Frontend E2E login → mount | P1 |

---

## 7. API Testing Standards

| Check | Tool |
| ----- | ---- |
| Status code | httpx AsyncClient |
| Envelope shape | assert code, data |
| Pagination | assert pagination.total |
| Permission | call without role → 403 |

Future: Postman/Newman collection from OpenAPI.

---

## 8. UI Testing 📋

Recommended: Playwright

| Flow | Priority |
| ---- | -------- |
| Login / logout | P0 |
| Quick create room | P0 |
| Mount device | P0 |
| Import devices | P1 |
| Contract CRUD | P2 |

---

## 9. Performance Testing 📋

Tool: Locust or k6

| Scenario | Target |
| -------- | ------ |
| Login TPS | 100 concurrent |
| Device list P95 | <500ms |
| Import 1000 rows | <10s |

---

## 10. Security Testing 📋

| Test | Tool |
| ---- | ---- |
| SAST Python | Bandit |
| Dependency scan | pip-audit |
| DAST | OWASP ZAP |
| RBAC bypass | Custom pytest |

---

## 11. CI/CD Integration Roadmap

| Step | Action |
| ---- | ------ |
| 1 | Add integration tests to CI with test DB |
| 2 | Add `pytest --cov` threshold (e.g. 60% → 90%) |
| 3 | Add frontend `npm run lint` |
| 4 | Add docker build smoke test |
| 5 | Nightly full suite + Locust |

Current CI definition: `.github/workflows/ci.yml`.

---

## 12. Acceptance Criteria (Release)

- [ ] All P0/P1 bugs closed
- [ ] Unit + integration tests pass
- [ ] Manual smoke: login → room → rack → mount → SVG
- [ ] Security checklist ([11-Security.md](11-Security.md))
- [ ] Docs version matches release tag

---

## References

- [05-API-Design.md](05-API-Design.md)
- [08-Layout-Engine.md](08-Layout-Engine.md)
- [12-Deployment.md](12-Deployment.md)
