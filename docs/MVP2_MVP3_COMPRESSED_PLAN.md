# ForgeForth Africa — Implementation Plan
## MVP 1, MVP 2 & MVP 3 (Rewritten March 10, 2026)

---

| Document Information | |
|---|---|
| **Version** | 4.0 |
| **Date** | March 10, 2026 |
| **Status** | Active — MVP1 in Final Completion |
| **Prepared by** | SynaVue Technologies |
| **Replaces** | Version 3.0 |

---

## Why We Rewrote This Plan

A lot has been built since the original plan was written. We now have a clear, honest picture of what exists in the codebase versus what is only planned. This document reflects reality.

**The core correction:**

Previous versions of this plan underestimated what MVP1 would cover. In practice, because the foundational subsystems — authentication, user accounts, talent profiles, organizations, and applications — are so tightly coupled to the website itself, a significant amount of that work was completed alongside the website. These subsystems now have real models, real views, real serializers, and real API endpoints. They belong in MVP1 as completed or near-completed work, not in MVP2 as future work.

**The result is a cleaner, more honest three-phase plan:**

| Phase | What It Is | Status |
|---|---|---|
| **MVP 1** | The Foundation — Website, Auth, Profiles, Orgs, Applications, Talent Portal | In final completion |
| **MVP 2** | The Intelligence Layer — Communications, Matching, Intelligence, Analytics, Admin Governance, Org Portal | Next phase |
| **MVP 3** | The Scale Layer — Mobile App, advanced DevOps, global scaling | Planned |

---

## Subsystem Mapping (Final)

| # | Subsystem | Phase | Real Status |
|---|---|---|---|
| 1 | Website & Blog | **MVP 1** | ✅ Live at forgeforthafrica.com |
| 2 | Security & Infrastructure | **MVP 1** | ✅ Deployed, config.json maintenance mode, SSL, middleware |
| 3 | Identity & Access Management (Auth Service) | **MVP 1** | ✅ Built — 3,314 lines, standalone service, HMAC-signed |
| 4 | User Accounts | **MVP 1** | ✅ Built — custom User model, roles, sessions, JWT |
| 5 | Talent Profiles | **MVP 1** | ✅ Built — full models, serializers, profile sections |
| 6 | Organizations & Opportunities | **MVP 1** | ✅ Built — 414+506+275 lines, full CRUD |
| 7 | Applications & Workflow | **MVP 1** | ✅ Built — 306+527+240 lines, status workflow |
| 8 | Secure Media Processing | **MVP 1** | ✅ Built — image pipeline, sanitization, WebP compression |
| 9 | Talent Portal | **MVP 1** | 🔄 In progress — templates + routes started, needs completion |
| 10 | Communication & Notification System | **MVP 2** | 🔲 Models done, views/logic not built |
| 11 | Talent Intelligence & Skill Extraction | **MVP 2** | 🔲 Models done, no views/logic |
| 12 | Matching & Recommendation Engine | **MVP 2** | 🔲 Models done, no views/logic |
| 13 | Analytics & Reporting | **MVP 2** | 🔲 Models done, no views/logic |
| 14 | Administration & Governance | **MVP 2** | 🔲 Models done, no views/logic |
| 15 | Organization Portal | **MVP 2** | 🔲 Not started |
| 16 | Mobile Application | **MVP 3** | 🔲 Not started |
| 17 | Advanced DevOps & Scaling | **MVP 3** | 🔲 Not started |

---

---

# MVP 1 — The Foundation
### Status: In Final Completion

**Theme:** The complete foundation of ForgeForth Africa. The website is live. The backend data layer for all core platform operations — authentication, profiles, organizations, and applications — is built and running. What remains is finishing the Talent Portal so users can actually log in and use everything we have already built.

**What MVP1 delivers when complete:**
- A live, professional website at forgeforthafrica.com
- Secure user registration and login (talent and organization accounts)
- Talent profile creation and management
- Organization registration and opportunity posting
- The ability for talent to apply to opportunities
- A talent portal where all of the above comes together in a usable interface

---

## What Is Already Done in MVP1

### Website & Blog — COMPLETE

The full informational website is live:
- 15+ pages: Home, About, For Talent, For Partners, Platform, Why Africa, Gallery, Contact, Blog, Privacy Policy, Terms of Service, Cookie Policy
- Blog with rich text editor, unique blog IDs, image upload with sanitization
- 112-language translation support via floating language switcher
- Glassmorphic, modern design with one.jpg hero background
- Registration modal (talent early access) and partner registration modal
- Contact form with WhatsApp, Call, Email, and Direct Message actions
- Admin dashboard at `/view/` with login, data tables, export to CSV and PDF
- Maintenance mode and coming soon mode via `config.json`
- Production deployed on cPanel with Gunicorn via `start.py`

### Security & Infrastructure — COMPLETE

- Custom middleware: maintenance mode, request logging, security headers
- `config.json` watched for real-time maintenance/coming-soon mode changes
- WhiteNoise for static file serving
- Jinja2 template engine for the website
- Django template engine for admin and portal views
- PostgreSQL database architecture (one DB per subsystem)
- Data orchestration service syncing subsystem DBs to central DB
- `start.py` handles full deployment: pip install, migrations, collectstatic, gunicorn launch
- `diagnose.py` for production troubleshooting

### Auth Service — COMPLETE

A standalone authentication service (`auth_service/`, 3,314 lines):
- Dedicated service running on port 9002
- Handles registration, login, logout, token refresh, email verification
- JWT access tokens (short-lived) + refresh tokens (long-lived)
- HMAC-SHA256 signed requests and responses — unsigned requests rejected silently
- Post-quantum safe signature verification layer
- Two-Factor Authentication (2FA): email OTP and TOTP authenticator app
- Password reset via email (time-limited token)
- Active session management — list and revoke sessions remotely
- Social login: Google OAuth2 and LinkedIn OAuth2
- Roles: Talent, Employer, Organization Admin, Platform Staff
- Full audit trail of all auth events

### User Accounts — COMPLETE

Custom `User` model in `accounts/` (full models, views, serializers):
- UUID primary keys
- Custom roles: Talent, Employer, Org Admin, Staff
- Email verification tokens
- Password reset tokens
- Session tracking with device info and IP
- 2FA secrets stored encrypted
- Account deactivation and POPIA-compliant deletion

### Talent Profiles — COMPLETE (models + serializers)

Full profile data layer in `profiles/` (models + 268-line serializers):
- Personal info: name, headline, location, availability, date of birth, gender
- Bio (markdown supported)
- Skills with proficiency levels and years of experience
- Work experience (multiple entries)
- Education (multiple entries, all qualification levels)
- Certifications and licenses
- Languages spoken with proficiency
- Portfolio links and project entries
- Opportunity preferences (types, work arrangement, industries, compensation, relocation)
- Profile completeness score (0–100%) calculation
- Profile visibility settings (Public / Registered / Organizations Only / Private)

### Organizations & Opportunities — COMPLETE

Full implementation in `organizations/` (414 models + 506 views + 275 serializers):
- Organization registration with verification workflow
- Organization profile: name, logo, type, industry, size, description, locations
- Team management: invite by email, assign Admin or Member roles, remove members
- All opportunity types: Full-time, Part-time, Internship, Volunteer, SkillUp, Freelance, Research
- Full opportunity fields: title, type, description, required skills, education, experience, location, compensation, deadline
- Opportunity status: Draft / Published / Paused / Closed
- Opportunity search and filtering

### Applications & Workflow — COMPLETE

Full implementation in `applications/` (306 models + 527 views + 240 serializers):
- Application submission with cover letter, CV upload, supporting documents
- Custom screening questions (up to 5 per opportunity, text/yes-no/multiple choice)
- Full status workflow: Submitted → Under Review → Shortlisted → Interview → Offer → Accepted → Placement Complete
- Rejection and withdrawal at appropriate stages
- Internal notes per applicant (private to organization)
- Bulk status updates
- Duplicate application prevention

### Secure Media Processing — COMPLETE

Image and document processing pipeline in `website/services/image_processor.py`:
- File type validation by magic bytes (not extension)
- Embedded malicious code scanning (PHP, JS, shell injections)
- Sanitization: dangerous patterns stripped, file continues processing
- EXIF and metadata stripping
- WebP conversion and compression (quality > 90%, size < 1MB)
- Thumbnail generation
- Organized storage structure under `media/` or AWS S3 when `USE_S3=True`
- Time-limited signed download URLs for private documents

---

## What Remains to Complete MVP1

### Talent Portal — IN PROGRESS

The talent portal (`talent_portal/`) has its foundation: routes, auth, API client, and starter templates. What needs to be completed:

**Authentication screens (started):**
- Login page — template exists at `talent_portal/templates/auth/login.html`
- Register page — template exists at `talent_portal/templates/auth/register.html`
- Both need to be wired to the auth service and fully functional

**Dashboard (started):**
- Template exists at `talent_portal/templates/dashboard/index.html`
- Needs: profile completeness widget, recent applications, notification feed, match recommendations (placeholder until MVP2)

**Profile Management (not started):**
- Multi-section profile editor: personal info, bio, skills, experience, education, certifications, portfolio, preferences
- Profile photo upload integrated with the image processing pipeline
- Completeness score display with improvement tips
- Visibility settings control

**Opportunity Discovery (started):**
- List template exists at `talent_portal/templates/opportunities/list.html`
- Needs: search bar, filters (type, location, industry, remote), sort options, bookmark button, apply button

**Application Tracker (not started):**
- List all applications with color-coded status indicators
- Status timeline view per application
- Withdrawal button on eligible applications
- Document view (see what was submitted)

**Profile View (started):**
- Template exists at `talent_portal/templates/profile/view.html`
- Needs: complete rendering of all profile sections as seen by visitors

**Settings (not started):**
- Account email and password change
- Profile visibility controls
- Notification preferences (ready for MVP2 notifications)
- Delete/deactivate account

**Messages (not started):**
- Inbox placeholder UI (messages arrive in MVP2 — UI can be built now with empty state)

### API Endpoints to Expose

All the models and views exist. The following endpoints need to be confirmed wired and tested:

| Endpoint | Status |
|---|---|
| `POST /api/v1/auth/register/talent/` | Built in auth_service |
| `POST /api/v1/auth/login/` | Built in auth_service |
| `GET /api/v1/profiles/me/` | Built in profiles |
| `PUT /api/v1/profiles/me/` | Built in profiles |
| `POST /api/v1/profiles/me/photo/` | Built, needs pipeline hookup |
| `GET /api/v1/opportunities/` | Built in organizations |
| `GET /api/v1/opportunities/search/` | Built in organizations |
| `POST /api/v1/applications/` | Built in applications |
| `GET /api/v1/applications/` | Built in applications |
| `POST /api/v1/applications/<id>/withdraw/` | Built in applications |

### MVP1 Completion Checklist

- [ ] Talent portal login and register pages fully wired to auth service
- [ ] Talent portal dashboard rendering real data (profile completeness, applications)
- [ ] Profile editor: all sections can be created and edited from the portal
- [ ] Profile photo upload working end-to-end through the image pipeline
- [ ] Opportunity discovery: search, filter, sort, bookmark, apply
- [ ] Application tracker: list with status, withdrawal working
- [ ] Settings page: password change, visibility, deactivate account
- [ ] All API endpoints confirmed working end-to-end
- [ ] Organization portal: basic dashboard, opportunity management, applicant tracker
- [ ] Email verification working after registration
- [ ] Password reset flow working end-to-end
- [ ] All profile sections rendering correctly on public profile page

**MVP1 Definition of Done:**
A talent can register, verify their email, log into the talent portal, build their profile, browse opportunities, apply to one, and track their application — all without any manual intervention. An organization can register, post an opportunity, receive applications, and move applicants through the workflow.

---

---

# MVP 2 — The Intelligence Layer
### Status: Next Phase (begins after MVP1 is complete)

**Timeline: 8–10 weeks**

**Theme:** Make the platform smart and connected. Every subsystem that has models-only in the codebase right now gets its full implementation: logic, views, API endpoints, and UI. The platform goes from a functional workflow tool to an intelligent, communicating, data-aware system.

**The Big Win:** By the end of MVP2, the platform communicates with users, understands their skills, recommends the right opportunities, and gives everyone — talent, organizations, and admins — the data they need to make good decisions.

---

## MVP 2 Goals

1. Email and in-app notifications keep users informed after every important event
2. Talent and organizations can message each other through the platform
3. The platform reads CVs and automatically suggests profile data
4. Every talent gets an employability score and skill gap analysis
5. The platform recommends the best opportunities to each talent
6. Organizations can discover the best-matching talent in the pool
7. Talent see personal analytics: profile views, application stats, skill demand trends
8. Organizations see pipeline analytics: applications per opportunity, time-to-fill, conversion
9. Platform admins have a full governance panel: user management, moderation, audit logs
10. The organization portal is fully complete

---

## MVP 2 Phase Timeline

| Weeks | Focus |
|---|---|
| 1–3 | Communications: email notifications for all events, in-app notification system |
| 2–4 | Messaging: talent-to-organization conversations, read receipts, file attachments |
| 3–6 | Intelligence: CV parser, employability score, skill gap analysis, career path suggestions |
| 5–8 | Matching: opportunity ranking by match score, candidate discovery, recommendation feeds |
| 5–7 | Analytics: talent analytics, organization analytics, platform-wide admin stats |
| 6–9 | Administration: user management, org moderation, content moderation, audit log, support tickets |
| 7–10 | Organization Portal: full build out of the org-side web portal |
| 9–10 | Integration testing, staging deployment, performance review |

---

## Subsystem 10 — Communication & Notification System
**Weeks 1–4**

The models are already built in `communications/models.py` (199 lines). This subsystem needs its views, service logic, Celery tasks, and API endpoints built out completely.

### What We Build

**Email Notifications via Celery:**

All emails are sent as background Celery tasks, not blocking the web request. Every significant platform event triggers an email:

| Event | Who Gets It | Content |
|---|---|---|
| Account registered | New user | Welcome message + email verification link |
| Email verified | New user | Confirmation + "here's what to do next" |
| Password reset requested | User | Reset link (expires in 1 hour) |
| New application received | Organization | Applicant name, opportunity title, link to review |
| Application submitted | Talent | Confirmation with application summary |
| Application status changed | Talent | New status in plain language + next steps |
| Application deadline in 3 days | Talent (saved opportunities) | Reminder with deadline |
| Team invitation sent | Invitee | Accept invitation link |
| Organization verified | Org Admin | Congratulations + what to do next |
| New message received | Recipient | Preview + link to conversation |
| Weekly opportunity digest | Talent | Top 5 matched opportunities this week |

Email templates are branded HTML (ForgeForth Africa logo, colors, mobile-responsive) with plain text fallbacks. All non-transactional emails include an unsubscribe link. Sent via SendGrid.

**In-App Notification System:**

- Notification bell icon in all portal headers with unread count badge
- Notification types: Application update / New message / New opportunity match / System alert / Platform announcement
- Mark single notification as read (click to navigate to relevant page)
- Mark all as read in one click
- Notification preferences per category — users can opt out of non-critical types
- Stored in the database, accessible via API

**Messaging System (Talent ↔ Organization):**

Application-linked conversations — a talent and organization can only exchange messages after the talent has applied (prevents unsolicited outreach):
- Conversation thread tied to a specific application
- Both parties can send text messages
- File attachments processed through the media pipeline (max 5 MB)
- Timestamps on all messages
- Read receipts: "Seen at 10:23 AM"
- Message inbox in both the talent portal and organization portal

### What Needs Building

- `communications/views.py` — full API view set (currently 3 lines placeholder)
- `communications/tasks.py` — Celery tasks for each notification type
- `communications/email_service.py` — SendGrid integration, template rendering
- `communications/urls.py` — updated with all endpoints
- Email HTML templates in `communications/templates/email/`
- Notification bell component in portal base templates
- Message inbox and conversation UI in both portals

### API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `GET /api/v1/notifications/` | GET | List my notifications (paginated) |
| `POST /api/v1/notifications/<id>/read/` | POST | Mark one as read |
| `POST /api/v1/notifications/read-all/` | POST | Mark all as read |
| `GET /api/v1/notifications/preferences/` | GET | Get notification preferences |
| `PUT /api/v1/notifications/preferences/` | PUT | Update notification preferences |
| `GET /api/v1/messages/conversations/` | GET | List my conversations |
| `GET /api/v1/messages/conversations/<id>/` | GET | Get all messages in a conversation |
| `POST /api/v1/messages/conversations/<id>/send/` | POST | Send a message |

---

## Subsystem 11 — Talent Intelligence & Skill Extraction
**Weeks 3–6**

The models are already built in `intelligence/models.py` (207 lines). This subsystem needs its CV parsing logic, scoring algorithms, and API layer built.

### What We Build

**CV / Resume Parsing:**

When a talent uploads a CV in the talent portal, the system automatically:
1. Extracts contact information (name, email, phone, location)
2. Extracts education history (institutions, qualifications, graduation years)
3. Extracts work experience (job titles, companies, durations, descriptions)
4. Maps extracted skills to our skill taxonomy (500+ skills, 10 categories)
5. Shows the talent a preview of everything found — they confirm or edit before saving
6. Flags any low-confidence extractions so the talent can review them
7. Populates their profile with one click

Target accuracy: above 85% on skill extraction.

Technology: PyMuPDF (PDF text extraction), python-docx (DOCX extraction), spaCy (NLP, named entity recognition), custom fuzzy matching against the taxonomy, confidence scoring per field.

**Skill Taxonomy:**
- 500+ skills across 10 categories: Technology, Healthcare, Finance, Creative Arts, Agriculture, Education, Trade and Technical, Business, Social Work, Other
- Synonyms handled (e.g., "JS" → "JavaScript")
- Skill relationships mapped (knowing React implies JavaScript)
- Demand weighting updated monthly from real opportunity data on the platform
- African-context skills included: mobile money, local regulatory knowledge, African language proficiency, community development, indigenous agricultural practices

**Employability Score (0–100):**

A score shown on the talent dashboard that signals profile strength for the opportunities they want:

| Component | Weight | How It Is Calculated |
|---|---|---|
| Profile completeness | 20% | Percentage of profile sections filled out |
| Skill relevance | 25% | Talent's skills vs. most in-demand skills on the platform |
| Experience depth | 20% | Years of experience plus seniority level |
| Education alignment | 15% | Education level vs. what their preferred opportunities require |
| Activity score | 10% | Frequency of logins and profile updates |
| Response rate | 10% | Percentage of messages and applications responded to |

The score comes with a breakdown and action items: "Your skill relevance is strong, but adding work experience would increase your score by 15 points."

**Skill Gap Analysis:**
- Compare talent's current skills to the top skills demanded in their preferred fields
- Show exactly what is missing: "Data Analysis roles on the platform require Python, Excel, and SQL. You have Python. You are missing Excel and SQL."
- Link to free and paid learning resources per skill gap

**Career Path Suggestions:**
- Based on current skills, show natural progression paths
- Example: "With your Python and data skills, you are 3 skills away from qualifying for Data Engineer roles"
- Powered by a skill-transition matrix built from platform application and placement data

**Profile Enhancement Tips:**
- Personalized, specific tips on the talent dashboard
- "Add a work experience entry to increase your score by 15 points"
- "Profiles with 200+ character bios get 3× more views from organizations"

### What Needs Building

- `intelligence/views.py` — API viewsets (currently 3 lines placeholder)
- `intelligence/services/cv_parser.py` — PyMuPDF + spaCy extraction logic
- `intelligence/services/skill_matcher.py` — taxonomy fuzzy matching
- `intelligence/services/scoring.py` — employability score calculation
- `intelligence/services/gap_analysis.py` — skill gap computation
- `intelligence/tasks.py` — Celery tasks for async CV processing
- `intelligence/data/taxonomy.json` — full skill taxonomy file
- Talent portal CV upload UI and extraction review screen

### API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `POST /api/v1/intelligence/parse-cv/` | POST | Upload CV and extract profile data |
| `GET /api/v1/intelligence/employability-score/` | GET | Get my current employability score |
| `GET /api/v1/intelligence/skill-gaps/` | GET | Get my skill gap analysis |
| `GET /api/v1/intelligence/career-paths/` | GET | Get suggested career paths |
| `GET /api/v1/intelligence/recommendations/` | GET | Get profile improvement tips |
| `GET /api/v1/intelligence/skills/taxonomy/` | GET | Browse the full skill taxonomy |
| `GET /api/v1/intelligence/skills/trending/` | GET | Top trending skills this month |

---

## Subsystem 12 — Matching & Recommendation Engine
**Weeks 5–8**

The models are already built in `matching/models.py` (156 lines). This subsystem needs its scoring logic, ranking algorithms, and API layer built.

### What We Build

**Talent to Opportunity Match Scoring:**

Every talent-opportunity pair gets a match score (0–100) calculated from:

| Factor | Weight | What It Measures |
|---|---|---|
| Skill overlap | 35% | Fraction of required skills the talent has |
| Experience level alignment | 20% | Talent's years of experience vs. the requirement |
| Education alignment | 10% | Qualification level vs. the minimum required |
| Location and remote preference | 15% | Does location match, or is remote offered and preferred? |
| Opportunity type preference | 10% | Does the talent want this type (job/internship/volunteer)? |
| Industry preference | 10% | Is this in an industry the talent selected as preferred? |

Every score is accompanied by a plain-language explanation shown to the talent:
> "87% match — You have 8 of 10 required skills. The role is remote, which matches your preference. It requires 2 years of experience and you have 3."

This is a core design principle: no black-box scores. Every number is explained.

**Opportunity Feed for Talents:**

On the talent dashboard and opportunities page, opportunities are ranked by match score rather than by date. The talent sees the most relevant opportunities first. The feed:
- Updates daily as new opportunities are posted
- Shows match score and top matching reason on each card
- Filters: by type, location, deadline, salary range
- "Recommended for You" section highlights the top 3 matches of the day

**Candidate Discovery for Organizations:**

Organizations can search the talent pool and get results ranked by match score for their specific opportunity:
- Filter by: required skills, experience level, education level, location, availability
- Each result shows: match score, matching skills highlighted, "Why this candidate?" summary
- "Find more like this" button on any candidate card
- Passive talent discovery — find great candidates who have not applied yet

**"Similar" Recommendations:**
- On any opportunity page: "5 similar opportunities you might also like"
- In the applicant view: "3 similar candidates currently in our talent pool"

### What Needs Building

- `matching/views.py` — API viewsets (currently 3 lines placeholder)
- `matching/services/scorer.py` — match score calculation engine
- `matching/services/ranker.py` — ranked list generation
- `matching/services/explainer.py` — plain-language explanation generation
- `matching/tasks.py` — Celery tasks for nightly score pre-computation
- Talent portal opportunity feed UI updated to show match scores
- Organization portal candidate search UI with match score display

### API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `GET /api/v1/matching/opportunities/` | GET | My ranked opportunity feed |
| `GET /api/v1/matching/opportunities/<id>/score/` | GET | Match score + explanation for one opportunity |
| `GET /api/v1/matching/candidates/` | GET | Ranked candidates for my opportunity |
| `GET /api/v1/matching/candidates/<id>/score/` | GET | Candidate match score + explanation |
| `GET /api/v1/matching/similar/opportunities/<id>/` | GET | Opportunities similar to this one |
| `GET /api/v1/matching/similar/candidates/<id>/` | GET | Candidates similar to this one |

---

## Subsystem 13 — Analytics & Reporting
**Weeks 5–7**

The models are already built in `analytics/models.py` (193 lines). This subsystem needs its aggregation logic, dashboard data APIs, and reporting tools built.

### What We Build

**Talent Personal Analytics (Talent Portal Dashboard):**
- Profile view count: total and weekly trend with a simple chart
- Search appearance count: how many times the talent appeared in organization searches
- Application breakdown by status: submitted, shortlisted, placed, rejected
- Organization response rate: percentage of applications that received any response
- Skill demand trend: "Is demand for your skills growing or declining on the platform?"
- Employability score history: chart showing improvement over the past 3 months
- "Your profile was viewed by 4 organizations this week" — contextual insight

**Organization Analytics (Organization Portal Dashboard):**
- Total applications received per opportunity
- Time-to-fill: days from posting to placement per opportunity
- Application funnel per opportunity: submitted → shortlisted → interview → offered → placed
- Conversion rate: what percentage of applicants reach placement
- Active opportunity performance: views, applications, bookmarks per posting
- Talent pool insights: geographic distribution of applicants

**Platform-Wide Analytics (Admin Only):**
- Total registered talents and organizations (growth over time)
- Total opportunities by type and status
- Total applications by status with conversion funnel
- Daily, weekly, and monthly new registrations chart
- Geographic distribution: country and city breakdown
- Most demanded skills across all active opportunities
- Language usage breakdown across the platform
- Top organizations by placements completed
- Platform health: average response rate, average time-to-fill

**Report Export:**
- Export any analytics view as CSV or PDF
- Scheduled weekly summary report emailed to admins and org admins automatically
- Custom date range selection on all charts and exports

### What Needs Building

- `analytics/views.py` — API viewsets (currently 3 lines placeholder)
- `analytics/services/aggregator.py` — data aggregation and computation
- `analytics/services/reporter.py` — CSV and PDF report generation
- `analytics/tasks.py` — Celery tasks for nightly analytics computation
- Talent portal analytics section in the dashboard
- Organization portal analytics dashboard
- Admin analytics panel in the `/view/` admin dashboard

### API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `GET /api/v1/analytics/me/` | GET | My personal talent analytics |
| `GET /api/v1/analytics/organization/<id>/` | GET | Organization analytics dashboard data |
| `GET /api/v1/analytics/platform/` | GET | Platform-wide stats — admin only |
| `GET /api/v1/analytics/skills/trending/` | GET | Trending skills across all opportunities |
| `GET /api/v1/analytics/geography/` | GET | Geographic distribution of users |
| `POST /api/v1/analytics/reports/generate/` | POST | Generate and download a CSV or PDF report |
| `POST /api/v1/analytics/reports/schedule/` | POST | Schedule an automated weekly report |

---

## Subsystem 14 — Administration & Governance
**Weeks 6–9**

The models are already built in `administration/models.py` (197 lines). This subsystem expands the existing `/view/` admin dashboard into a full governance and management platform.

### What We Build

**User Management:**
- View all users with filters: role, status, registration date, last active
- View any individual user's full profile, activity history, and application log
- Suspend an account: user sees "Account Suspended" on login, cannot access the platform
- Unsuspend an account
- Permanently delete an account with POPIA-compliant data purging (removes personal data within 30 days, retains anonymized aggregate records)
- Impersonate a user for support purposes — every impersonation session is logged in the audit trail
- Manually verify a user's email if they did not receive the verification email
- Reset any user's password on their behalf (sends reset email to user)

**Organization Management:**
- View all organizations with filters: type, industry, verification status, date registered
- Verify or revoke verification for any organization
- View organization's complete team, all opportunities, and full applicant history
- Suspend an organization's account (all their opportunities are paused automatically)
- Remove specific opportunities that violate platform guidelines

**Opportunity Moderation:**
- Optional moderation queue: newly posted opportunities can be held for review before going public
- Approve: opportunity goes live
- Reject with reason: organization is notified by email with the rejection reason
- Minor edits: admin can correct small issues without returning to the organization
- Feature flag: mark an opportunity as featured (appears at top of search results)
- Auto-flagging: opportunities containing suspicious keywords are held for review automatically

**Content Moderation:**
- View all flagged or reported content (profiles, blogs, messages)
- Remove inappropriate content
- Issue a formal warning to a user (stored in their account record, visible to all admins)
- Temporary ban (specify duration)
- Permanent ban

**Platform Configuration UI:**
- `maintenance_mode` toggle — on/off (updates `config.json` in real time)
- `oncoming` mode toggle — shows coming soon page
- Feature flags: enable or disable specific features without code deployment
- API rate limit adjustments per user tier
- Site-wide announcement banner text management
- Email template management

**Audit Log:**
- Every admin action is logged: which admin, what action, which object, when, from which IP
- Filter by: admin user, action type, date range, affected object
- Cannot be modified or deleted — append-only by design
- Exportable as CSV for compliance and legal review

**Support Ticket System:**
- Users submit support tickets from their portal under "Help"
- Admin sees all tickets with status: Open / In Progress / Resolved
- Admin replies by typing in the admin panel — reply is emailed to the user automatically
- Close ticket with a resolution note
- Ticket history retained permanently

**Broadcast and Announcement System:**
- Admin composes a message with subject and body (rich text)
- Select recipients: All Users / All Talents / All Organizations / Specific user by email
- Delivery: In-app notification / Email / Both
- Schedule: send now or at a specified future date and time
- View all sent broadcasts and their delivery statistics

### What Needs Building

- `administration/views.py` — expanded from 3 lines to full management views
- `administration/services/moderation.py` — content flagging and review logic
- `administration/services/audit.py` — audit trail write and read functions
- `administration/services/broadcast.py` — bulk notification and email dispatch
- `administration/tasks.py` — scheduled report delivery, auto-flagging Celery tasks
- Expanded `/view/` admin dashboard: new tabs for Users, Organizations, Opportunities, Audit Log, Support, Broadcasts

### API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `GET /api/v1/administration/users/` | GET | List all users with filters |
| `GET /api/v1/administration/users/<id>/` | GET | View a specific user |
| `POST /api/v1/administration/users/<id>/suspend/` | POST | Suspend a user |
| `POST /api/v1/administration/users/<id>/unsuspend/` | POST | Unsuspend a user |
| `DELETE /api/v1/administration/users/<id>/` | DELETE | POPIA-compliant account deletion |
| `POST /api/v1/administration/organizations/<id>/verify/` | POST | Verify an organization |
| `POST /api/v1/administration/opportunities/<id>/moderate/` | POST | Approve or reject an opportunity |
| `GET /api/v1/administration/audit-log/` | GET | View audit log with filters |
| `GET /api/v1/administration/config/` | GET | View platform configuration |
| `PUT /api/v1/administration/config/` | PUT | Update platform configuration |
| `GET /api/v1/administration/tickets/` | GET | List all support tickets |
| `POST /api/v1/administration/tickets/<id>/reply/` | POST | Reply to a support ticket |
| `POST /api/v1/administration/broadcasts/` | POST | Create and send a broadcast |

---

## Subsystem 15 — Organization Portal
**Weeks 7–10**

The organization portal does not yet exist as a web interface (the org API is built, but there is no portal UI). This subsystem builds the full organization-facing web portal.

### What We Build

**Portal at `/org/` (port 9004):**

*Dashboard:*
- Applications received today and this week
- Active and paused opportunities count
- Top-matched candidates currently in the talent pool
- Recent activity feed

*Opportunity Manager:*
- Create new opportunity (full form: all fields, screening questions)
- List all opportunities with status indicators
- Edit, publish, pause, or close any opportunity
- View per-opportunity analytics (views, applications, bookmarks)

*Applicant Tracker:*
- Per-opportunity list of all applicants
- Filter and sort: by match score, status, skills, location
- Click into any applicant to see their full profile
- Move applicant through workflow stages
- Add internal notes
- Bulk status updates
- Message applicant button (opens conversation)

*Team Management:*
- View all team members with their roles
- Invite a new team member by email
- Change a member's role
- Remove a member

*Organization Profile Editor:*
- Edit all organization fields: name, logo, description, industry, size, locations, website, social links

*Analytics:*
- Time-to-fill charts
- Application funnel per opportunity
- Talent pool insights

*Settings:*
- Account settings
- Notification preferences
- Billing information (placeholder for future monetization)
- Logout

### What Needs Building

- `talent_portal/` equivalent directory structure for org portal
- All org portal HTML templates (Jinja2 or Django templates)
- Portal routes in `forgeforth/urls.py`
- Role-based access: only Org Admin and Org Member can access
- API client layer calling the organizations, applications, matching, and analytics APIs

---

## MVP 2 Completion Checklist

**Communications:**
- [ ] Email notifications firing for all events listed above
- [ ] Email templates branded and mobile-responsive
- [ ] In-app notification bell working in talent and org portals
- [ ] Notification preferences settable per category
- [ ] Talent-to-organization messaging working with read receipts

**Intelligence:**
- [ ] CV parser extracting skills with above 85% accuracy
- [ ] Employability scores calculated and shown on talent dashboard
- [ ] Skill gap analysis showing what is missing and why
- [ ] Career path suggestions appearing on talent dashboard
- [ ] Profile enhancement tips shown with score impact

**Matching:**
- [ ] Opportunity feed ranked by match score for all talents
- [ ] Every match score accompanied by a plain-language explanation
- [ ] Candidate discovery ranked by match score for organizations
- [ ] "Similar opportunities" section on opportunity pages
- [ ] "Similar candidates" shown in org applicant view

**Analytics:**
- [ ] Talent analytics section live on talent portal dashboard
- [ ] Organization analytics dashboard live on org portal
- [ ] Platform-wide admin analytics in `/view/` dashboard
- [ ] CSV and PDF report export working
- [ ] Scheduled weekly report emails working

**Administration:**
- [ ] User management: suspend, unsuspend, delete with data purge
- [ ] Organization verification workflow in admin UI
- [ ] Opportunity moderation queue operational
- [ ] Audit log viewer accessible and exportable
- [ ] Support ticket system: submit, reply, close
- [ ] Broadcast system: compose, schedule, deliver

**Organization Portal:**
- [ ] Opportunity creation and management fully functional
- [ ] Applicant tracker with match scores and workflow management
- [ ] Team management working
- [ ] Organization profile editor working
- [ ] Analytics dashboard live

**MVP2 Success Metrics:**
- 500+ registered users (talents + organizations)
- 50+ active opportunities posted
- 200+ applications submitted
- Email delivery rate above 95%
- Match scores rated as useful by at least 70% of users surveyed
- Zero security incidents in the first 30 days post-launch

---

---

# MVP 3 — The Scale Layer
### Status: Planned (begins after MVP2 is complete)

**Timeline: 6–8 weeks**

**Theme:** Put ForgeForth Africa in every pocket and prepare the platform for serious scale. MVP3 is about reach (mobile app) and robustness (advanced infrastructure, monitoring, and DevOps).

**The Big Win:** By the end of MVP3, ForgeForth Africa is accessible to any African with a smartphone, and the platform can scale from thousands to hundreds of thousands of users without breaking.

---

## MVP 3 Goals

1. Native mobile apps on iOS and Android give the full platform experience on any smartphone
2. Push notifications keep users engaged even when away from their browser
3. The infrastructure can handle 100,000+ concurrent users without degradation
4. Monitoring and alerting give the team visibility into every part of the platform
5. CI/CD pipelines mean new features ship in minutes, not hours

---

## Subsystem 16 — Mobile Application
**Weeks 1–6**

### Technology

**React Native** — a single codebase that produces native apps for both iOS and Android. All business logic stays on the server. The mobile app is a frontend client calling the same REST APIs built in MVP1 and MVP2.

### What We Build

**Authentication Screens:**
- Animated splash screen with ForgeForth Africa branding
- Onboarding: 3 screens explaining what the platform is and who it is for
- Register: talent or organization selection, then the appropriate form
- Login: email and password
- Social login: Google and LinkedIn
- 2FA entry screen
- Biometric login on subsequent sessions (Face ID / fingerprint) using the device keychain

**Talent Mobile Experience:**

*Home:*
- Personalized opportunity feed ranked by match score
- Match score shown on each opportunity card
- Notification bell with unread count
- Quick stats: applications sent this week, profile views

*Profile:*
- View and edit all profile sections from the phone
- Upload photo from camera or gallery (compressed client-side before upload)
- Completeness score with improvement tips
- Share profile link

*Opportunities:*
- Browse with search and filters (type, location, remote, industry)
- Opportunity detail showing match score and explanation
- Save to bookmarks
- Apply: cover letter input, CV attach from phone storage

*Applications:*
- List with color-coded status indicators
- Status progress bar showing current stage
- Withdraw button
- Tap to message the organization

*Messages:*
- Conversation list with unread indicators
- Chat view with timestamps and read receipts
- File attach from device

*Settings:*
- Account: email, password change
- Notification preferences
- Language selection
- Privacy and visibility settings
- Logout

**Organization Mobile Experience:**

*Dashboard:* Applications today, active opportunities, top candidates
*Opportunities:* List, create, edit, pause, close
*Applicants:* Review profiles, update status, message
*Settings:* Org profile, team, account

**Technical Features:**
- Offline mode: last 7 days of data cached and readable without internet
- Push notifications via Firebase Cloud Messaging
- Deep linking: email links open directly inside the app
- Background sync: data refreshes when app comes to foreground
- Secure token storage using iOS Keychain and Android Keystore
- Certificate pinning to prevent man-in-the-middle attacks
- Session timeout: auto-logout after 30 minutes of inactivity

**App Store Submission:**
- iOS: Apple App Store (requires Apple Developer Program account, $99/year)
- Android: Google Play Store (requires Google Developer account, $25 one-time)

**Mobile-Specific API Additions:**
- `POST /api/v1/mobile/device/register/` — register FCM token for push notifications
- `POST /api/v1/mobile/sync/checkpoint/` — get list of changes since last sync
- `POST /api/v1/auth/biometric/challenge/` — server-side biometric session verification

---

## Subsystem 17 — Advanced DevOps & Scaling
**Weeks 4–8**

### What We Build

**Infrastructure Upgrade:**
- Migrate from shared cPanel hosting to a dedicated VPS or cloud instance (AWS, DigitalOcean, or Hetzner)
- Nginx as the reverse proxy in front of Gunicorn
- Multiple Gunicorn worker processes configured for CPU count
- Redis cluster for cache and Celery broker
- PostgreSQL with read replicas for analytics queries

**CI/CD Pipeline (GitHub Actions):**
- On every push to `main`: run tests, lint, build
- On every tagged release: automatic deployment to production
- Database migration step included in deployment pipeline
- Rollback procedure: previous release can be re-deployed in under 2 minutes

**Monitoring & Alerting:**
- Sentry for error tracking: every unhandled exception captured with context
- Uptime monitoring: alert within 1 minute if any service goes down
- Performance monitoring: p95 response time tracked per endpoint
- Database query monitoring: slow queries (above 500ms) flagged automatically
- Celery task monitoring: failed tasks alerted immediately

**Security Hardening:**
- Automatic SSL certificate renewal (Let's Encrypt via Certbot)
- WAF (Web Application Firewall) rules for common attack patterns
- Rate limiting per IP for all public endpoints
- Automated vulnerability scanning on each deployment
- Regular automated database backups with 30-day retention

**Load Testing:**
- Load test every major release to 10,000 concurrent users
- Performance budget: homepage loads in under 1 second at 10,000 concurrent users
- API response time budget: 95th percentile under 200ms for read endpoints

---

## MVP 3 Completion Checklist

**Mobile App:**
- [ ] React Native app builds successfully for iOS and Android
- [ ] All authentication flows working (register, login, 2FA, biometric)
- [ ] Full talent experience: profile, opportunities, applications, messages
- [ ] Full organization experience: dashboard, opportunities, applicants
- [ ] Push notifications delivered via Firebase for all key events
- [ ] Offline mode working: cached data readable without internet
- [ ] Deep linking from email notifications to app working
- [ ] Both apps submitted to App Store and Google Play Store
- [ ] Both apps approved and publicly downloadable

**DevOps & Scaling:**
- [ ] Migrated to dedicated server or cloud
- [ ] CI/CD pipeline deploying automatically on each release
- [ ] Sentry error tracking active in production
- [ ] Uptime monitoring with 1-minute alert threshold
- [ ] Database backups automated with verified restore procedure
- [ ] Load test completed successfully at 10,000 concurrent users

**MVP3 Success Metrics:**
- Mobile app live on both stores with a rating of 4.0 stars or above
- Push notification open rate above 15%
- Platform uptime above 99.5%
- Zero unmonitored production errors
- API p95 response time under 200ms

---

---

# Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.9+ |
| Backend Framework | Django 4.2 LTS |
| REST API | Django REST Framework 3.14 |
| WebSockets | Django Channels |
| Template Engine | Jinja2 3.1 (website), Django templates (admin + portals) |
| Styling | Tailwind CSS |
| Database per Service | PostgreSQL |
| Central Database | PostgreSQL (unified, for cross-service queries) |
| Cache | Redis |
| Task Queue | Celery + Redis |
| File Storage | Local filesystem (dev), AWS S3 af-south-1 (prod) |
| Email Provider | SendGrid |
| CV Parsing | PyMuPDF + spaCy |
| Mobile | React Native |
| Push Notifications | Firebase Cloud Messaging |
| Web Server | Gunicorn |
| Reverse Proxy | Apache (cPanel) → Nginx (dedicated server, MVP3) |
| Static Files | WhiteNoise |
| CI/CD | GitHub Actions (MVP3) |
| Error Tracking | Sentry (MVP3) |

---

# Dependency Map

```
MVP 1 (In Final Completion)
├── Website + Blog ─────────────────────────── DONE
├── Auth Service ───────────────────────────── DONE (3,314 lines)
├── Accounts ───────────────────────────────── DONE (models + views + serializers)
├── Profiles ───────────────────────────────── DONE (models + serializers)
├── Organizations + Opportunities ──────────── DONE (full implementation)
├── Applications + Workflow ────────────────── DONE (full implementation)
├── Media Processing ───────────────────────── DONE (image pipeline)
└── Talent Portal ──────────────────────────── IN PROGRESS (templates started)

MVP 2 (Next — 8–10 weeks)
├── Communications ◄── Auth + Applications (MVP1)
├── Intelligence ◄───── Profiles + Media (MVP1)
├── Matching ◄────────── Intelligence + Profiles + Organizations (MVP1 + above)
├── Analytics ◄─────────── All MVP1 data sources
├── Administration ◄──── All subsystems (governs everything)
└── Organization Portal ◄── Organizations + Applications + Matching + Analytics

MVP 3 (After MVP2 — 6–8 weeks)
├── Mobile App ◄──── All MVP1 + MVP2 APIs
└── DevOps & Scaling ◄── All subsystems at production load
```

---

# Full Roadmap Summary

| Phase | Status | Timeline | Key Deliverable |
|---|---|---|---|
| **MVP 1** | 🔄 Final completion | Now | Full platform foundation live: website, auth, profiles, orgs, applications, talent portal |
| **MVP 2** | 📋 Planned | 8–10 weeks | Intelligence layer: comms, matching, AI, analytics, admin governance, org portal |
| **MVP 3** | 📋 Planned | 6–8 weeks | Scale layer: mobile apps, dedicated infrastructure, CI/CD, monitoring |

**Total to complete the full platform: 14–18 weeks from today**

---

# Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| CV parser accuracy below 85% | Medium | Medium | Manual fallback + user correction UI always available, user confirms before saving |
| Talent portal completion delays MVP1 | Medium | High | Prioritize core flows: login, profile edit, apply — defer settings and advanced UI |
| Mobile app store rejection | Low | High | Follow Apple and Google guidelines strictly, test on real devices, no undocumented permissions |
| Email deliverability issues | Medium | High | Use SendGrid, warm up sending domain, monitor bounce rates weekly |
| Database migration errors | Low | High | Always backup before any migration, test on staging environment first |
| Matching engine quality | Medium | Medium | Show scores with explanations so users can give feedback, iterate based on data |
| Scope creep in mobile | High | Medium | Strict feature freeze before mobile development starts |
| PostgreSQL on shared hosting | Medium | High | SQLite fallback in dev, migrate to VPS when traffic grows beyond shared hosting limits |

---

*© 2026 ForgeForth Africa. All Rights Reserved.*
*Prepared by SynaVue Technologies — www.synavue.com*
*Document Version: 4.0 | March 10, 2026*

