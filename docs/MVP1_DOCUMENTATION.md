# ForgeForth Africa - MVP1 Documentation

## Enterprise Talent Infrastructure Platform

---

| Document Information | |
|---------------------|---|
| **Version** | 1.0 |
| **Date** | March 7, 2026 |
| **Phase** | MVP1 (Minimum Viable Product - Phase 1) |
| **Status** | Complete |
| **Prepared by** | SynaVue Technologies |

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [MVP1 Overview](#2-mvp1-overview)
3. [Website Pages](#3-website-pages)
4. [User Registration System](#4-user-registration-system)
5. [Blog System](#5-blog-system)
6. [Multi-Language Support](#6-multi-language-support)
7. [Administrative Dashboard](#7-administrative-dashboard)
8. [Security Features](#8-security-features)
9. [Database Structure](#9-database-structure)
10. [Deployment](#10-deployment)
11. [Technical Details](#11-technical-details)
12. [Completion Summary](#12-completion-summary)

---

## 1. Introduction

### What is ForgeForth Africa?

ForgeForth Africa is a talent infrastructure platform that connects African talent with opportunities. Our core belief is simple: **"There is power beyond a poor résumé."**

We recognize that traditional hiring systems often prioritize well-formatted CVs over actual skills. A brilliant developer might be overlooked because their résumé doesn't look professional enough. A talented craftsperson might never get noticed because they don't know how to write a cover letter.

ForgeForth Africa changes this by focusing on what people can actually do, not just what their documents say.

### Geographic Scope

The platform serves all 54 African countries, from Cairo, Egypt to Cape Town, South Africa. We support 112 languages to ensure accessibility across the continent's diverse linguistic landscape.

### Core Message

**"We are changing how Africa works, thinks, and becomes."**

---

## 2. MVP1 Overview

### What is MVP1?

MVP1 (Minimum Viable Product - Phase 1) is the foundational release of ForgeForth Africa. This phase establishes our online presence and builds the infrastructure for future features.

### MVP1 Goals

1. **Launch a complete informational website** - Tell the world who we are and what we do
2. **Collect early interest** - Allow talents and partners to register for early access
3. **Build content foundation** - Create a blog platform for thought leadership
4. **Support language diversity** - Enable the website in 112 languages
5. **Establish technical foundation** - Build a secure, scalable architecture

### What MVP1 Includes

| Category | Items |
|----------|-------|
| **Website Pages** | 15 complete pages |
| **Registration** | Talent and Partner registration forms |
| **Blog** | Full blog system with editor |
| **Languages** | 112 language translations |
| **Admin** | Dashboard for managing registrations |
| **Security** | POPIA-compliant data protection |

### What MVP1 Does NOT Include

- User login system (users register but cannot log in yet)
- Talent profiles and dashboards
- Organization portals
- Job/opportunity matching
- Messaging between users
- Mobile application

These features are planned for future phases.

---

## 3. Website Pages

### 3.1 Complete Page List

| Page | URL | Purpose |
|------|-----|---------|
| Home | `/` | Main landing page |
| About Us | `/about/` | Company story and values |
| For Talent | `/for-talent/` | Information for job seekers |
| For Partners | `/for-employers/` | Information for organizations |
| Platform | `/platform/` | How the platform works |
| Why Africa | `/why-africa/` | Our focus on Africa |
| Blog | `/blog/` | Articles and insights |
| Blog Article | `/blog/<slug>/` | Individual blog posts |
| Gallery | `/gallery/` | Photo gallery |
| Contact | `/contact/` | Contact information and form |
| Privacy Policy | `/privacy-policy/` | Data privacy information |
| Terms of Service | `/terms-of-service/` | Usage terms |
| Cookie Policy | `/cookie-policy/` | Cookie information |
| Error 404 | N/A | Page not found |
| Error 500 | N/A | Server error |
| Maintenance | N/A | Shown during maintenance |
| Coming Soon | N/A | Pre-launch page |

### 3.2 Home Page

**URL:** `/`

**Sections:**
- Hero section with Africa map background image
- "What if I told you Africa is rich?" - Five cards showing Africa's wealth (resources, minerals, talent, culture, opportunity)
- The Problem - Explaining challenges African talent faces
- Our Solution - How ForgeForth Africa addresses these challenges
- Platform features overview
- Call-to-action buttons for registration

**Design Features:**
- Full-screen hero with glassmorphic overlay
- Rotating geometric circles animation
- 3D hover effects on cards
- Africa-themed imagery

### 3.3 About Us Page

**URL:** `/about/`

**Content:**
- Company founding story
- Mission statement: "To empower African talent by providing a platform that goes beyond traditional résumés"
- Vision statement: "A world where African talent is recognized based on actual skills and potential"
- Core values: Empowerment, Connection, Innovation, Integrity, Excellence
- "We are changing how Africa works, thinks, and becomes" emphasis section

### 3.4 For Talent Page

**URL:** `/for-talent/`

**Content:**
- Benefits of joining as talent
- Types of opportunities available:
  - Full-time jobs
  - Internships
  - Volunteer programs
  - Skill-up programs
- How the registration process works
- Registration call-to-action button

### 3.5 For Partners Page

**URL:** `/for-employers/`

**Content:**
- Partnership benefits for organizations
- Types of organizations we work with:
  - Companies
  - NGOs
  - Government agencies
  - Educational institutions
- Partnership models available
- Partner registration call-to-action button

**Note:** This page focuses on empowering and connecting, not just hiring.

### 3.6 Platform Page

**URL:** `/platform/`

**Content:**
- How ForgeForth Africa works (explained simply)
- "One Platform. Two Journeys." section with cards for:
  - Professionals (talent journey)
  - Organizations (partner journey)
- Key platform features
- Security and privacy highlights
- Read more links to For Talent and For Partners pages

### 3.7 Why Africa Page

**URL:** `/why-africa/`

**Content:**
- "What if I told you Africa is rich?" theme
- Africa's riches explained:
  - Natural resources
  - Minerals
  - **Talent** (highlighted as our focus)
  - Culture
  - Opportunity
- Geographic scope: "From Cairo, Egypt to Cape Town, South Africa"
- Africa map image
- Statistics about African talent potential

### 3.8 Blog Page

**URL:** `/blog/`

**Features:**
- List of all published blog articles
- Search functionality
- Category filtering
- Pagination for large numbers of articles
- Each article shows:
  - Title
  - Excerpt
  - Featured image
  - Author
  - Publication date
  - Read time estimate

### 3.9 Individual Blog Articles

**URLs:** 
- `/blog/<slug>/` (by article slug)
- `/blog/p/<unique-id>/` (by unique 8-character ID for sharing)

**Features:**
- Full article content with rich formatting
- Featured image
- Author information
- Publication date
- Social sharing buttons
- Related articles suggestions
- View count tracking

### 3.10 Gallery Page

**URL:** `/gallery/`

**Features:**
- Grid layout of images
- Lightbox for full-size viewing
- Category filtering
- Responsive masonry layout for different screen sizes

### 3.11 Contact Page

**URL:** `/contact/`

**Features:**
- Contact form with fields:
  - Full name
  - Email
  - Phone number
  - Country
  - Message
- Four quick action buttons:
  - **WhatsApp:** Opens WhatsApp to +27 69 297 3425
  - **Call:** Direct call to +27 69 297 3425
  - **Email:** Opens email to contact@forgeforthafrica.com
  - **Direct Message:** Coming soon indicator
- Office location: South Africa

### 3.12 Legal Pages

**Privacy Policy (`/privacy-policy/`):**
- POPIA (Protection of Personal Information Act) compliant
- What data we collect
- How we use data
- User rights (access, correction, deletion)
- Data retention periods
- Third-party services used
- Contact for privacy concerns

**Terms of Service (`/terms-of-service/`):**
- Acceptance of terms
- User responsibilities
- Prohibited activities
- Intellectual property rights
- Limitation of liability
- Termination conditions
- Dispute resolution

**Cookie Policy (`/cookie-policy/`):**
- Types of cookies used
- Purpose of each cookie type
- How to manage cookies
- Third-party cookies

### 3.13 Error Pages

**404 Page (Page Not Found):**
- Friendly error message
- Link back to home page
- Search suggestion

**500 Page (Server Error):**
- Apologetic error message
- Contact information for support
- Link back to home page

### 3.14 Special Pages

**Maintenance Mode Page:**
- Displayed when `maintenance_mode: 1` in config.json
- Informs users the site is temporarily unavailable
- Estimated return time (optional)
- Social media links

**Coming Soon Page:**
- Displayed when `oncoming: 1` in config.json
- Teaser content about the platform
- Email signup for launch notification
- Social media links

---

## 4. User Registration System

### 4.1 Talent Registration

Individuals can register their interest in the platform through a modal form.

**Fields Collected:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Full Name | Text | Yes | User's complete name |
| Email | Email | Yes | Contact email |
| Phone | Phone | Yes | With country code |
| Date of Birth | Date | Yes | For age verification |
| Gender | Dropdown | Yes | Male/Female/Other/Prefer not to say |
| Country | Text | Yes | Country of residence |
| City | Text | No | City of residence |
| Brief Bio | Text area | No | Up to 500 characters |
| Skills | Multi-select | Yes | Choose from list |
| Preferred Fields | Multi-select | Yes | Areas of interest |
| Opportunity Types | Multi-select | Yes | Job/Internship/Volunteer/Skill-up |

**Skills Categories Available:**
- Technology (Programming, Web Development, Data Science, Cybersecurity, etc.)
- Creative (Graphic Design, Writing, Photography, Video, Music, etc.)
- Business (Marketing, Finance, Sales, Management, HR, etc.)
- Healthcare (Nursing, Medicine, Pharmacy, Public Health, etc.)
- Education (Teaching, Training, Curriculum Development, etc.)
- Trades (Construction, Electrical, Plumbing, Mechanics, etc.)
- Agriculture (Farming, Agribusiness, Food Processing, etc.)
- Other (with custom input field)

**Consent Checkboxes (all required):**
- ✅ I am 18 years or older
- ✅ I consent to ForgeForth Africa storing and processing my data
- ✅ I have read and understood the Privacy Policy
- ✅ I have read and understood the Terms of Service
- ✅ I understand that providing accurate information improves my chances

**After Submission:**
- Data saved to database
- Success message displayed: "You are a step closer to transforming Africa. We have reserved your space in ForgeForth Africa."
- Form clears

### 4.2 Partner Registration

Organizations can register their interest in partnering with ForgeForth Africa.

**Fields Collected:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Organization Name | Text | Yes | Company/org name |
| Organization Type | Dropdown | Yes | Company/NGO/Government/Education/Other |
| Industry | Dropdown | Yes | Primary industry |
| Contact Person | Text | Yes | Primary contact name |
| Email | Email | Yes | Business email |
| Phone | Phone | Yes | Business phone |
| Country | Text | Yes | Organization location |
| Company Size | Dropdown | Yes | 1-10/11-50/51-200/201-500/500+ |
| Partnership Interests | Multi-select | Yes | Types of engagement |
| Additional Info | Text area | No | Other relevant details |

**Industry Options:**
- Technology
- Finance & Banking
- Healthcare
- Education
- Manufacturing
- Agriculture
- Retail
- Hospitality
- Construction
- Energy
- Transportation
- Media & Entertainment
- Government
- Non-Profit
- Other (with custom input)

**Partnership Interest Options:**
- Hiring talent
- Internship programs
- Volunteer programs
- Skills development
- Corporate partnerships
- Sponsorships
- Research collaboration
- Other (with custom input)

**After Submission:**
- Data saved to database
- Success message displayed
- Admin notified (when email configured)

### 4.3 Data Storage

Registration data is stored in database tables:

**Talent Registrations Table (`website_waitlistentry`):**
- id (auto-generated UUID)
- name, email, phone, date_of_birth, gender
- country, city
- bio
- skills (JSON array)
- preferred_fields (JSON array)
- opportunity_types (JSON array)
- ip_address (not shown to admins)
- created_at (timestamp)
- is_read (boolean)
- is_contacted (boolean)

**Partner Registrations Table (`website_partnerregistration`):**
- id (auto-generated UUID)
- organization_name, organization_type
- industry
- contact_person, email, phone
- country, company_size
- partnership_interests (JSON array)
- additional_info
- ip_address (not shown to admins)
- created_at (timestamp)
- is_read (boolean)
- is_contacted (boolean)

---

## 5. Blog System

### 5.1 Overview

The blog allows ForgeForth Africa to publish articles about talent, skills, opportunities, and African workforce development.

### 5.2 Blog Features

**For Readers:**
- Browse all articles
- Search by keyword
- Filter by category
- Read full articles
- Share articles via unique ID link
- View related articles

**For Authors (Admin):**
- Create new articles at `/blog/write/`
- Rich text editor with formatting:
  - Bold, italic, underline
  - Headings (H1 through H6)
  - Bullet and numbered lists
  - Links
  - Images
  - Code blocks
  - Block quotes
- Upload featured images
- Assign categories and tags
- Save as draft or publish immediately

### 5.3 Blog Article Structure

Each blog article has:

| Field | Description |
|-------|-------------|
| Title | Article headline (max 200 characters) |
| Slug | URL-friendly version of title |
| Unique ID | 8-character ID for sharing |
| Content | Full article body (HTML) |
| Excerpt | Short summary (max 500 characters) |
| Featured Image | Main image for the article |
| Category | Single category assignment |
| Tags | Multiple tags (JSON array) |
| Author | Writer's name |
| Status | Draft or Published |
| Views | Number of times viewed |
| Created At | When first created |
| Updated At | When last modified |
| Published At | When made public |

### 5.4 Image Processing

All uploaded images go through security and optimization:

**Security Steps:**
1. Remove all metadata (EXIF, GPS, camera info)
2. Scan for malicious code patterns (PHP, JavaScript)
3. Verify file type matches extension
4. Check for embedded executables

**Optimization Steps:**
1. Convert to WebP format (better compression)
2. Maintain quality above 90%
3. Reduce file size to under 1MB
4. Resize if larger than 2000x2000 pixels

**Storage:**
Images are stored in folders organized by blog ID:
```
website/blog_media/
└── <blog-unique-id>/
    ├── featured.webp
    ├── image_001.webp
    └── image_002.webp
```

### 5.5 URL Structure

| URL Pattern | Purpose |
|-------------|---------|
| `/blog/` | List all articles |
| `/blog/<slug>/` | Article by URL slug |
| `/blog/p/<id>/` | Article by unique ID |
| `/blog/write/` | Create new article |

The unique ID URLs are useful for sharing because they're short and never change, even if the article title is updated.

---

## 6. Multi-Language Support

### 6.1 Overview

ForgeForth Africa supports 112 languages to serve users across Africa and beyond.

### 6.2 Languages Supported

**African Languages (selected):**
| Language | Code |
|----------|------|
| Swahili | sw |
| Amharic | am |
| Hausa | ha |
| Yoruba | yo |
| Zulu | zu |
| Afrikaans | af |
| Igbo | ig |
| Xhosa | xh |
| Somali | so |
| Oromo | om |
| Tigrinya | ti |
| Shona | sn |
| Kinyarwanda | rw |
| Chichewa | ny |
| Malagasy | mg |
| Sesotho | st |
| Setswana | tn |

**International Languages (selected):**
| Language | Code |
|----------|------|
| English | en |
| French | fr |
| Portuguese | pt |
| Arabic | ar |
| Spanish | es |
| Chinese | zh |
| German | de |
| Japanese | ja |
| Korean | ko |
| Hindi | hi |
| Russian | ru |

Plus 90+ additional languages covering Europe, Asia, and other regions.

### 6.3 How Translation Works

1. User clicks the language selector button (floating circle, bottom-left)
2. Modal opens showing all 112 languages with search
3. User selects desired language
4. Google Translate translates the page content
5. User's preference is saved in browser storage
6. Future visits remember the language preference

### 6.4 Protected Elements

Certain content is NOT translated to maintain consistency:

- **ForgeForth Africa** (brand name)
- Email addresses (e.g., contact@forgeforthafrica.com)
- Phone numbers
- URLs and links
- Form field labels
- Technical terms

These are marked with `class="notranslate"` or `translate="no"` attribute.

### 6.5 Language Selector Design

**Button:**
- Circular floating button
- Position: bottom-left corner
- Shows flag of currently selected language
- Flag fills the entire circle
- 3D glassmorphic design
- Hover animation

**Modal:**
- Glassmorphic design
- Search box at top
- Languages grouped by region (Africa, Europe, Asia, etc.)
- Each language shows:
  - Flag icon
  - Language name in English
  - Language name in native script
- Click to select and translate immediately

---

## 7. Administrative Dashboard

### 7.1 Overview

The admin dashboard at `/view/` allows authorized users to manage registrations and messages.

### 7.2 Access

**URL:** `/view/`

**Login:**
- Password-protected page
- Session-based authentication
- Auto-logout after inactivity

### 7.3 Dashboard Tabs

**Tab 1: Messages**
- Shows all contact form submissions
- Columns: Name, Email, Phone, Country, Message preview, Date, Status
- Click any row to see full message in popup modal
- Mark as read/unread
- Mark as contacted/not contacted

**Tab 2: Registrations (Talents)**
- Shows all talent registrations
- Columns: Name, Email, Phone, Skills, Fields, Opportunities, Date
- Click any row to see full details in popup modal
- Mark as read/unread
- Mark as contacted/not contacted

**Tab 3: Partners**
- Shows all partner registrations
- Columns: Organization, Type, Industry, Contact, Email, Size, Date
- Click any row to see full details in popup modal
- Mark as read/unread
- Mark as contacted/not contacted

### 7.4 Detail Modals

When clicking a row, a popup shows all details:

**Message Detail:**
- Full name
- Email (clickable)
- Phone (clickable tel: link)
- Country
- Full message text
- Submission date/time
- Actions: Mark read, Mark contacted

**Talent Detail:**
- All personal information
- Full bio
- All selected skills (formatted list)
- All preferred fields (formatted list)
- All opportunity types
- Registration date/time

**Partner Detail:**
- Organization information
- Contact person details
- All partnership interests
- Additional notes
- Registration date/time

### 7.5 Export Functionality

**Export Button:** Opens modal with export options

**Export Types:**
- All Data (messages + talents + partners)
- Messages Only
- Talents Only
- Partners Only

**Export Formats:**
- CSV (opens in Excel)
- PDF (formatted report)

**PDF Report Features:**
- ForgeForth Africa logo at top
- 3D container around logo
- Formatted data tables
- Footer text: "This is a system generated document"
- Copyright notice with year
- Filename format: `{type}_{timestamp}.pdf`

### 7.6 Logout

- Logout button in dashboard
- Confirmation modal: "Are you sure you want to logout?"
- Clears session data
- Redirects to login page

---

## 8. Security Features

### 8.1 Form Security

| Protection | How It Works |
|------------|--------------|
| CSRF Tokens | Every form includes a unique token to prevent cross-site attacks |
| Input Validation | All inputs are validated on both client and server |
| HTML Escaping | User input is escaped to prevent code injection |
| Rate Limiting | 100 requests/hour for anonymous users |

### 8.2 Data Protection

| Protection | Implementation |
|------------|----------------|
| HTTPS | All traffic encrypted in production |
| Password Hashing | Using Django's PBKDF2 with SHA256 |
| Secure Cookies | HttpOnly and Secure flags enabled |
| Session Security | Server-side sessions with secure tokens |

### 8.3 Image Upload Security

Every uploaded image is processed:

1. **Metadata Removal:** Strips EXIF, GPS, camera data
2. **Code Detection:** Scans for `<?php`, `<%`, `<script>` patterns
3. **Type Verification:** Checks actual file content, not just extension
4. **Size Limits:** Maximum 10MB upload, 1MB after processing

### 8.4 Security Headers

```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: same-origin
```

In production:
```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

### 8.5 Compliance

**POPIA (South Africa):**
- Clear privacy policy
- Explicit consent checkboxes
- Data minimization (only collect what's needed)
- Right to access personal data
- Right to request deletion
- Data breach notification procedures

**GDPR Principles:**
- Lawful, fair, transparent processing
- Purpose limitation
- Data minimization
- Accuracy
- Storage limitation
- Security

---

## 9. Database Structure

### 9.1 Database System

**Production:** PostgreSQL
**Development/Fallback:** SQLite

### 9.2 MVP1 Tables

**website_waitlistentry (Talent Registrations):**
```
id              UUID (primary key)
name            VARCHAR(200)
email           VARCHAR(254)
phone           VARCHAR(50)
date_of_birth   DATE
gender          VARCHAR(50)
country         VARCHAR(100)
city            VARCHAR(100)
bio             TEXT
skills          JSON
preferred_fields JSON
opportunity_types JSON
ip_address      VARCHAR(45)
created_at      TIMESTAMP
is_read         BOOLEAN
is_contacted    BOOLEAN
```

**website_partnerregistration (Partner Registrations):**
```
id                    UUID (primary key)
organization_name     VARCHAR(200)
organization_type     VARCHAR(100)
industry              VARCHAR(100)
contact_person        VARCHAR(200)
email                 VARCHAR(254)
phone                 VARCHAR(50)
country               VARCHAR(100)
company_size          VARCHAR(50)
partnership_interests JSON
additional_info       TEXT
ip_address            VARCHAR(45)
created_at            TIMESTAMP
is_read               BOOLEAN
is_contacted          BOOLEAN
```

**website_contactmessage (Contact Form Messages):**
```
id          UUID (primary key)
name        VARCHAR(200)
email       VARCHAR(254)
phone       VARCHAR(50)
country     VARCHAR(100)
message     TEXT
ip_address  VARCHAR(45)
created_at  TIMESTAMP
is_read     BOOLEAN
is_contacted BOOLEAN
```

**website_blogpost (Blog Articles):**
```
id              UUID (primary key)
title           VARCHAR(200)
slug            VARCHAR(200) UNIQUE
unique_id       VARCHAR(8) UNIQUE
content         TEXT
excerpt         VARCHAR(500)
featured_image  VARCHAR(500)
category        VARCHAR(100)
tags            JSON
author          VARCHAR(100)
status          VARCHAR(20)
views           INTEGER
created_at      TIMESTAMP
updated_at      TIMESTAMP
published_at    TIMESTAMP
```

### 9.3 Multi-Database Architecture

MVP1 establishes the foundation for a multi-database system:

| Database | Purpose |
|----------|---------|
| db_central | Core website data, blogs, registrations |
| db_accounts | User authentication (future) |
| db_profiles | Talent profiles (future) |
| db_organizations | Company data (future) |
| db_applications | Job applications (future) |
| db_communications | Messages (future) |
| db_analytics | Usage metrics (future) |
| db_media | File references (future) |
| db_intelligence | AI/ML data (future) |
| db_security | Audit logs (future) |

In MVP1, all data uses the central database. The multi-database structure is prepared for future scaling.

---

## 10. Deployment

### 10.1 Production Environment

| Component | Configuration |
|-----------|---------------|
| Domain | forgeforthafrica.com |
| Web Server | Apache |
| Application | Gunicorn with 4 workers |
| Database | PostgreSQL (or SQLite fallback) |
| Static Files | WhiteNoise |
| SSL | Provided by hosting |

### 10.2 Configuration Files

**`.env` file:**
```
DJANGO_ENV=production
DEBUG=False
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=forgeforthafrica.com,www.forgeforthafrica.com
DATABASE_URL=your-database-url
```

**`config.json` file:**
```json
{
  "maintenance_mode": 0,
  "oncoming": 0,
  "version": "1.0.0"
}
```

### 10.3 Deployment Script

The `start.py` script handles deployment:

1. Checks Python version (requires 3.9+)
2. Detects virtual environment
3. Upgrades pip
4. Installs requirements from requirements.txt
5. Loads environment variables from .env
6. Initializes config.json if missing
7. Creates necessary directories (logs, staticfiles, mediafiles)
8. Runs Django system checks
9. Applies database migrations
10. Collects static files
11. Starts Gunicorn server

### 10.4 Maintenance Mode

**To enable:** Set `maintenance_mode` to `1` in config.json

**What happens:**
- All pages show maintenance message
- Changes take effect immediately (no restart needed)
- Admin can still access via specific IP allowlist

**To disable:** Set `maintenance_mode` to `0` in config.json

### 10.5 Coming Soon Mode

**To enable:** Set `oncoming` to `1` in config.json

**What happens:**
- All pages redirect to Coming Soon page
- Shows teaser content
- Allows email collection for launch notification

### 10.6 Health Check

**Endpoint:** `/health`

**Returns:**
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0"
}
```

Used by monitoring systems to verify the site is running.

---

## 11. Technical Details

### 11.1 Technology Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.9+ |
| Framework | Django 4.2 |
| API | Django REST Framework 3.14 |
| Templates | Jinja2 3.1 |
| Styling | Tailwind CSS |
| JavaScript | Vanilla JS |
| Database | PostgreSQL / SQLite |
| Cache | Redis |
| Task Queue | Celery 5.3 |
| Web Server | Gunicorn |
| Static Files | WhiteNoise |

### 11.2 Python Dependencies

```
Django>=4.2,<4.3
djangorestframework==3.14.0
django-cors-headers==4.3.1
django-filter==23.5
django-redis==5.4.0
django-extensions==3.2.3
celery==5.3.6
redis==5.0.1
Pillow==10.2.0
python-dotenv==1.0.0
whitenoise==6.6.0
gunicorn==21.2.0
Jinja2>=3.1
```

### 11.3 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/talent-waitlist/` | POST | Submit talent registration |
| `/api/partner-waitlist/` | POST | Submit partner registration |
| `/api/contact/` | POST | Submit contact message |
| `/health` | GET | Health check |

### 11.4 File Structure

```
forgeforth/
├── forgeforth/           # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── website/              # Main website app
│   ├── templates/
│   │   └── website/
│   │       ├── layouts/
│   │       │   └── base.html
│   │       ├── pages/
│   │       │   ├── index.html
│   │       │   ├── about.html
│   │       │   └── ...
│   │       ├── components/
│   │       │   ├── navbar.html
│   │       │   └── footer.html
│   │       └── errors/
│   │           ├── 404.html
│   │           └── 500.html
│   ├── static/
│   │   └── website/
│   │       ├── css/
│   │       ├── js/
│   │       └── images/
│   ├── blog_media/       # Blog images
│   ├── models.py
│   ├── views.py
│   └── urls.py
├── accounts/             # User accounts app (structure only)
├── profiles/             # Talent profiles app (structure only)
├── organizations/        # Organizations app (structure only)
├── ...                   # Other apps (structure only)
├── config.json           # Runtime configuration
├── .env                  # Environment variables
├── requirements.txt      # Python dependencies
├── start.py              # Deployment script
└── manage.py             # Django management
```

---

## 12. Completion Summary

### 12.1 What Was Built

**Website (15 pages):**
- ✅ Home page with hero, problem/solution, features
- ✅ About Us with mission, vision, values
- ✅ For Talent information page
- ✅ For Partners information page
- ✅ Platform overview page
- ✅ Why Africa page
- ✅ Blog listing and article pages
- ✅ Gallery page
- ✅ Contact page with multi-channel options
- ✅ Privacy Policy (POPIA compliant)
- ✅ Terms of Service
- ✅ Cookie Policy
- ✅ 404 error page
- ✅ 500 error page
- ✅ Maintenance mode page
- ✅ Coming soon page

**Functionality:**
- ✅ Talent registration modal with skills selection
- ✅ Partner registration modal
- ✅ Contact form with WhatsApp, Call, Email buttons
- ✅ Blog system with rich text editor
- ✅ Image upload with security processing
- ✅ 112 language translation support
- ✅ Admin dashboard with tabs
- ✅ Data export to CSV and PDF
- ✅ Maintenance mode toggle
- ✅ Coming soon mode toggle
- ✅ Health check endpoint

**Technical:**
- ✅ Django project with modular apps
- ✅ PostgreSQL database support
- ✅ Multi-database architecture foundation
- ✅ Security implementation (CSRF, input validation, etc.)
- ✅ POPIA/GDPR compliance measures
- ✅ Production deployment configuration
- ✅ Automated deployment script

### 12.2 MVP1 Status

| Category | Items | Completed | Status |
|----------|-------|-----------|--------|
| Pages | 15+ | 15+ | ✅ 100% |
| Features | 12 | 12 | ✅ 100% |
| Technical | 6 | 6 | ✅ 100% |
| **Total MVP1** | **33** | **33** | **✅ 100%** |

### 12.3 Production URL

**Website:** https://forgeforthafrica.com

---

## Contact Information

**ForgeForth Africa**

📧 Email: contact@forgeforthafrica.com  
📱 Phone: +27 69 297 3425  
🌐 Website: www.forgeforthafrica.com

**Partnership Inquiries:** partnerships@forgeforthafrica.com

**Headquarters:** South Africa

---

**Development Partner:**  
SynaVue Technologies  
www.synavue.com

---

*© 2026 ForgeForth Africa. All Rights Reserved.*

*This document is confidential and intended for authorized recipients only.*

