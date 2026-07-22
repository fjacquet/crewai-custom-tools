# Subagent-Driven Development Progress Ledger

## Phase 1: Core Toolkit Consolidation (Completed)

| Task | Component | Status | Commits | Review | Notes |
|---|---|---|---|---|---|
| Task 1 | Package Dependencies & Setup | Complete | 9ea1d2a..e7c3962 | Clean | All core dependencies configured & lockfile successfully compiled |
| Task 2 | Core Resiliency & SHA-256 Cache | Complete | e7c3962..b515748 | Clean | SHA-256 caching and non-blocking ThreadPoolExecutor timeout decorators implemented |
| Task 3 | Centralized Pydantic Models | Complete | 74a7d62..94b90e2 | Clean | All pre-existing Pydantic models migrated, structured, and exported successfully |
| Task 4 | Unified Web & Search Tools | Complete | 94b90e2..115fd46 | Clean | Consolidated Perplexity, Serper, Wikipedia, scraper with fallbacks, and RSS tools |
| Task 5 | Unified Finance & Crypto Tools | Complete | 115fd46..9e00c67 | Clean | Consolidated yfinance ticker metrics, company info, ETF holdings, CoinMarketCap, Kraken, FRED, Fear/Greed, and Exchange Rates tools |
| Task 6 | Unified OSINT & Cyber Recon | Complete | 9e00c67..a6d2d6e | Clean | Consolidated GitHub, email intelligence, Username check, crt.sh subdomains, RDAP WHOIS, and French corporate registers tools |
| Task 7 | Rich Document/Report Generators | Complete | a6d2d6e..c2c628e | Clean | Migrated HTML report layout renders, structural validators, dynamic PDF compiler, and Pestel/Financial builders |
| Task 8 | Enterprise APIs & Main Exports | Complete | c2c628e..7ea2714 | Clean | Consolidated Todoist, Airtable, Accuweather, and RAG tools, and exposed public API namespace |

## Phase 2: OSINTFR Curated Tools Integration (Roadmap Expansion)

| Task | Component | Status | Commits | Review | Notes |
|---|---|---|---|---|---|
| Task 1 | Setup Dependencies & Schemas | Complete | d7b7bef..c99c73b | Clean | Configured holehe dependency and added centralized Epieos, Holehe, and OpenCorporates schemas |
| Task 2 | Epieos & Holehe Email Tools | Complete | c99c73b..70ea350 | Clean | Implemented EpieosLookupTool and Holehe platform scanning tools with mock-based unit tests |
| Task 3 | OpenCorporates Global Search | Complete | 70ea350..ba18f86 | Clean | Implemented OpenCorporatesSearchTool with hybrid keyless fallbacks and mock-based unit tests |
| Task 4 | Public Exports & Verification | Complete | ba18f86..76d9ab2 | Clean | Exposed Epieos, Holehe, and OpenCorporates at package root with complete smoke tests |

## Phase 3: v0.3.0 epic_news superset fixes (Plan 1)

Plan: epic_news/docs/superpowers/plans/2026-07-08-crewai-custom-tools-v0.3.0-upstream-fixes.md
Branch: feat/v0.3.0-epic-news-superset (off main @ ef43361)
Goal: SaveToRag rag_tool injection + UnifiedRss output-file/scraping restore → tag v0.3.0.
Note: PAUSE for user confirmation before the push/tag in Task 4.

- BASE(Task1) = ef43361. Task 1 dispatched (implementer: haiku).
- Task 1: complete (commit 20f6f23, review clean/Approved). MINOR (plan-mandated, for final review): `rag_tool: Any = None` field is dead — `__init__` stores on `self._rag_tool`, so `.rag_tool` stays None; epic_news test_rag_tools reads `_rag_tool` so no break. Follow-up: drop field or forward via super().__init__.
- BASE(Task2) = 20f6f23. Task 2 dispatched (implementer: sonnet).
- Task 2: complete (commit 41c4a5a, review Approved; full suite 227/227). Notes (plan-mandated, informational): _scraper scaffolding inert until Task 3; invalid_sources conflates errored+empty (moot — epic_news consumer never passes invalid_sources_file_path). Trailers verified on both commits.
- BASE(Task3) = 41c4a5a. Task 3 dispatched (implementer: sonnet).
- Task 3: complete (commit 66658a2, review Approved; full suite 229). Newspaper3k optional lazy import + scraper-envelope fallback + invalid-sources file all verified; 2 new tests assert real file output.
- Plan 1 implementation (Tasks 1-3) COMPLETE. Task 4 = release: local prep (Steps 1-8) via implementer; push/tag (Steps 9-11) held for USER CONFIRMATION.
- BASE(Task4) = 66658a2. Task 4 (Steps 1-8 only) dispatched (implementer: haiku).
- Task 4 local prep: complete (release commit was 679674d, review Approved; full suite 229). Controller amended uv.lock (self-version 0.2.0→0.3.0, missed by brief Step 8 staging) into the release commit → now 2d9e546. Trailer preserved; tree clean.
- PLAN 1 LOCAL COMPLETE. Branch feat/v0.3.0-epic-news-superset: 20f6f23, 41c4a5a, 66658a2, 2d9e546. Suite 229 green.
- PAUSED for user confirmation before push/tag/release (Steps 9-11).
- User chose PR→merge→tag. PR #2 opened; CI green (3.11/3.12/3.13); CodeRabbit: 2 Major (tz cutoff, feed timeout) — both faithful ports of epic_news prod behavior, NOT regressions. User chose merge-as-is + follow-ups: filed issues #3 (tz) + #4 (timeout), replied to CodeRabbit.
- PLAN 1 COMPLETE & RELEASED: PR #2 merged (main a33a7ab), tag v0.3.0 pushed, GitHub release live. Smoke OK (version 0.3.0; SaveToRag rag_tool ✓; UnifiedRss signature ✓). epic_news git-pin @v0.3.0 resolves. → proceed to Plan 2.
- Task 3 (Steps 1-3+6) : commit 11f8a0d. Contrôleur a vérifié : diff = exactement 3 lignes de heading, `gh release list` inchangé (v0.24.0 toujours Latest), arbre propre. Steps 4-5 EN ATTENTE d'accord humain.
- Task 3: complete (commit 11f8a0d, spec ✅ / Approved, zéro finding). Humain a relu l'artefact et approuvé la publication. 3 releases publiées : v0.25.0, v0.26.0, v0.27.0. Vérifié : v0.27.0 est « Latest » ; restent sans release exactement les 10 anciens tags hors périmètre (v0.1.1, v0.4.0, v0.5.0, v0.5.1, v0.6.0, v0.19.2, v0.19.3, v0.20.0, v0.21.0, v0.21.1).
- Toutes les tâches terminées. Revue finale de branche à dispatcher.
- Revue finale de branche (opus) : « Ready to merge with fixes », 0 Critical. Vérifié hors CI : 38/38 headings rendent un corps non vide, encodage robuste sous locale ASCII, aucune surface d'injection (corps via --notes-file), ruff clean sur scripts/. 3 Important : (1) section VIDE publie une release vide — la spec le promettait, le code ne le fait pas, et ci.yml ne se déclenche pas sur les tags donc aucun test ne couvre ce chemin ; (2) CLAUDE.md dit `git push --tags` qui ne pousse pas la branche → release pour un commit sur aucune branche ; (3) interdiction absolue de `gh release create` sans procédure de reprise. Minor hérités 1-3 : tous « à laisser ».
- Humain a choisi : 3 Important + Minor 4 (tomllib.load binaire), 6 (ruff sur scripts), 7 (test OSError), 8 (Commands block). Un seul sous-agent de correction dispatché.
- Correctifs de revue : commit f18b3f5 (8 points du lot, 13 tests dans test_extract_changelog, suite 1027). Le sous-agent a signalé 2 résidus hors périmètre, corrigés par le contrôleur en e4e53e2 : CLAUDE.md:31 annonçait encore `ruff check src tests` sans `scripts`, et spec §6 citait encore `git push --tags`. Le plan garde sa formulation d'origine (compte rendu de l'exécuté, pas consigne). Re-revue dispatchée sur 11f8a0d..e4e53e2.
- Re-revue : « Fixes verified: Yes / Ready to merge: Yes », 0 Critical, 0 Important. Les 7 findings + 2 résidus fermés avec preuve fichier:ligne. Garde anti-corps-vide revérifiée par exécution sur les 38 headings réels : aucun faux positif, y compris sur les 4 sections sans `---` et la dernière du fichier. MINOR restant corrigé par le contrôleur (0d47c05) : `git tag -a -f` sans `-m` ouvre un éditeur. MINOR laissé : `open()` sans context manager dans le `python -c` du workflow (processus qui se termine aussitôt).
- BRANCHE COMPLÈTE. 7 commits. Suite 1027 verte, ruff propre sur src/tests/scripts.
