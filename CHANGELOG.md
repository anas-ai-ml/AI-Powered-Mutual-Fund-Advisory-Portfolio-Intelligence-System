# Changelog

All notable changes to this project are documented in this file.

## [2.0.0] - 2026-03-28

### Added
- Versioned engine structure under `backend/engines/v2/`.
- Refactored risk engine in `backend/engines/v2/risk_engine.py`.
- Expanded goal engine in `backend/engines/v2/goal_engine.py`.
- Explanation standards module in `backend/engines/v2/explanation_standards.py`.
- Investment mode recommendation engine in `backend/engines/v2/investment_mode_engine.py`.
- Feature-flag-driven engine routing in top-level engine wrappers.

### Changed
- Top-level `backend/engines/risk_engine.py` now routes between `v2` and `v1` via `v2_risk_explanation`.
- Top-level `backend/engines/goal_engine.py` now routes between `v2` and `v1` via `advanced_goal_types`.
- Top-level `backend/engines/explanation_standards.py` now routes between `v2` and `v1` via `v2_risk_explanation`.
- Top-level `backend/engines/investment_mode_engine.py` now routes between `v2` and fallback logic via `investment_mode_recommendation`.

### Configuration
- Added `FEATURE_FLAGS` in `config.py`:
  - `v2_risk_explanation`
  - `advanced_goal_types`
  - `investment_mode_recommendation`
  - `advanced_products`

## [1.0.0] - Initial Release

### Added
- Baseline planning engines under `backend/engines/v1/`.
- Initial risk scoring, goal planning, recommendation, projection, and Monte Carlo modules.
