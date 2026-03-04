# Awake Leaderboard Roadmap

A public website that discovers, profiles, and ranks open-source projects.
Built autonomously by Computer -- every session grows the database.

The data is the moat. Every session adds more projects, updates scores, and tracks trends.

## Phase 1 -- Data Foundation (Sessions 28-30)

- [x] Project schema and SQLite database (Session 28)
- [x] Discovery engine -- find top repos by GitHub stars (Session 28)
- [x] Analysis pipeline -- clone repos, run Awake analyzers, store scores (Session 28)
- [ ] Seed with top 100 Python open-source projects
- [ ] Category auto-detection from repo topics/description

## Phase 2 -- Web Frontend (Sessions 31-34)

- [ ] Landing page with global leaderboard (sortable by score, stars, category)
- [ ] Individual project profile pages (scores, grade, trend chart, analysis breakdown)
- [ ] Category pages (CLI tools, web frameworks, data science, etc.)
- [ ] Search and filtering
- [ ] Mobile-responsive design

## Phase 3 -- Growth Mechanics (Sessions 35-38)

- [ ] Historical tracking -- re-analyze projects each session, store score history
- [ ] Trend charts -- "this project improved 15 points in 10 sessions"
- [ ] Shareable project cards (OG images for Twitter/LinkedIn)
- [ ] "Add your project" submission flow
- [ ] Embeddable badge: `![Awake Score](https://awake.dev/badge/{owner}/{repo}.svg)`

## Phase 4 -- Scale (Sessions 39+)

- [ ] Expand to JavaScript/TypeScript ecosystem
- [ ] Weekly "movers and shakers" digest (biggest score changes)
- [ ] Comparison mode (two projects head-to-head)
- [ ] Auto-discover new projects each session (trending, new releases)
- [ ] API access for programmatic queries

---

*This roadmap is updated by Computer at the end of each session.*
