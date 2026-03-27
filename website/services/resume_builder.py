# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Intelligent Resume Builder Service
======================================================
A professional, AI-powered resume builder with:
- Multiple professional templates
- Real-time preview
- ATS optimization scoring
- AI-powered content suggestions
- PDF/DOCX export
- Smart formatting
"""
import logging
import json
import re
import io
import os
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ResumeTemplate(Enum):
    """Available resume templates."""
    PROFESSIONAL = "professional"
    MODERN = "modern"
    CREATIVE = "creative"
    MINIMAL = "minimal"
    EXECUTIVE = "executive"
    TECH = "tech"
    ACADEMIC = "academic"


class SectionType(Enum):
    """Resume section types."""
    HEADER = "header"
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILLS = "skills"
    CERTIFICATIONS = "certifications"
    PROJECTS = "projects"
    LANGUAGES = "languages"
    AWARDS = "awards"
    PUBLICATIONS = "publications"
    VOLUNTEER = "volunteer"
    REFERENCES = "references"
    CUSTOM = "custom"


@dataclass
class ResumeSection:
    """A single resume section."""
    section_type: SectionType
    title: str
    content: Any
    order: int = 0
    is_visible: bool = True
    custom_title: Optional[str] = None


@dataclass
class PersonalInfo:
    """Personal information for resume header."""
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    headline: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    portfolio_url: str = ""
    website: str = ""
    photo_url: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


@dataclass
class ExperienceEntry:
    """Work experience entry."""
    id: str = ""
    job_title: str = ""
    company: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    is_current: bool = False
    description: str = ""
    achievements: List[str] = field(default_factory=list)
    skills_used: List[str] = field(default_factory=list)


@dataclass
class EducationEntry:
    """Education entry."""
    id: str = ""
    institution: str = ""
    degree: str = ""
    field_of_study: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    is_current: bool = False
    gpa: str = ""
    achievements: List[str] = field(default_factory=list)


@dataclass
class SkillEntry:
    """Skill entry with proficiency."""
    name: str = ""
    level: str = "intermediate"  # beginner, intermediate, advanced, expert
    category: str = ""
    years: int = 0


@dataclass
class CertificationEntry:
    """Certification entry."""
    id: str = ""
    name: str = ""
    issuer: str = ""
    issue_date: str = ""
    expiry_date: str = ""
    credential_id: str = ""
    credential_url: str = ""


@dataclass
class ProjectEntry:
    """Project entry."""
    id: str = ""
    name: str = ""
    description: str = ""
    url: str = ""
    technologies: List[str] = field(default_factory=list)
    start_date: str = ""
    end_date: str = ""


@dataclass
class ResumeData:
    """Complete resume data structure."""
    personal_info: PersonalInfo = field(default_factory=PersonalInfo)
    summary: str = ""
    experience: List[ExperienceEntry] = field(default_factory=list)
    education: List[EducationEntry] = field(default_factory=list)
    skills: List[SkillEntry] = field(default_factory=list)
    certifications: List[CertificationEntry] = field(default_factory=list)
    projects: List[ProjectEntry] = field(default_factory=list)
    languages: List[Dict[str, str]] = field(default_factory=list)
    awards: List[Dict[str, str]] = field(default_factory=list)
    volunteer: List[Dict[str, Any]] = field(default_factory=list)
    custom_sections: List[Dict[str, Any]] = field(default_factory=list)

    # Settings
    template: str = "professional"
    section_order: List[str] = field(default_factory=lambda: [
        "summary", "experience", "education", "skills",
        "certifications", "projects", "languages"
    ])
    color_scheme: str = "default"
    font_family: str = "inter"
    show_photo: bool = False


class ATSOptimizer:
    """
    ATS (Applicant Tracking System) Optimization Engine.
    Analyzes resume content for ATS compatibility.
    """

    # Common ATS-friendly action verbs
    ACTION_VERBS = {
        'achieved', 'accomplished', 'administered', 'analyzed', 'built',
        'collaborated', 'conceptualized', 'conducted', 'consolidated', 'coordinated',
        'created', 'delivered', 'demonstrated', 'designed', 'developed',
        'directed', 'drove', 'enabled', 'engineered', 'established',
        'evaluated', 'executed', 'expanded', 'facilitated', 'founded',
        'generated', 'guided', 'headed', 'identified', 'implemented',
        'improved', 'increased', 'initiated', 'innovated', 'integrated',
        'launched', 'led', 'managed', 'maximized', 'mentored',
        'negotiated', 'optimized', 'orchestrated', 'organized', 'oversaw',
        'partnered', 'pioneered', 'planned', 'produced', 'programmed',
        'reduced', 'reengineered', 'resolved', 'restructured', 'revamped',
        'spearheaded', 'standardized', 'streamlined', 'strengthened', 'supervised',
        'transformed', 'upgraded', 'utilized', 'validated', 'verified'
    }

    # Words to avoid
    WEAK_WORDS = {
        'responsible for', 'duties included', 'worked on', 'helped with',
        'assisted with', 'was involved in', 'participated in', 'team player',
        'hard worker', 'detail-oriented', 'go-getter', 'synergy', 'leverage'
    }

    @classmethod
    def analyze(cls, resume_data: ResumeData) -> Dict[str, Any]:
        """
        Analyze resume for ATS optimization.
        Returns a score and detailed feedback.
        """
        score = 100
        issues = []
        suggestions = []
        strengths = []

        # Check personal info completeness
        personal_score, personal_issues = cls._check_personal_info(resume_data.personal_info)
        score -= (20 - personal_score)
        issues.extend(personal_issues)

        # Check summary
        if resume_data.summary:
            summary_score, summary_issues, summary_suggestions = cls._check_summary(resume_data.summary)
            score -= (15 - summary_score)
            issues.extend(summary_issues)
            suggestions.extend(summary_suggestions)
            if summary_score >= 12:
                strengths.append("Professional summary is well-written")
        else:
            score -= 10
            issues.append("Missing professional summary - highly recommended for ATS")

        # Check experience
        if resume_data.experience:
            exp_score, exp_issues, exp_suggestions = cls._check_experience(resume_data.experience)
            score -= (30 - exp_score)
            issues.extend(exp_issues)
            suggestions.extend(exp_suggestions)
            if exp_score >= 25:
                strengths.append("Work experience is detailed with quantifiable achievements")
        else:
            score -= 20
            issues.append("No work experience listed")

        # Check education
        if resume_data.education:
            edu_score, edu_issues = cls._check_education(resume_data.education)
            score -= (15 - edu_score)
            issues.extend(edu_issues)
            if edu_score >= 12:
                strengths.append("Education section is complete")
        else:
            score -= 10
            issues.append("No education listed")

        # Check skills
        if resume_data.skills:
            skills_score = min(15, len(resume_data.skills) * 2)
            score -= (15 - skills_score)
            if len(resume_data.skills) >= 5:
                strengths.append(f"Good skill coverage with {len(resume_data.skills)} skills listed")
            elif len(resume_data.skills) < 3:
                suggestions.append("Add more relevant skills - aim for 8-15 skills")
        else:
            score -= 10
            issues.append("No skills listed - critical for ATS keyword matching")

        # Ensure score is within bounds
        score = max(0, min(100, score))

        # Determine grade
        if score >= 90:
            grade = "A"
            grade_label = "Excellent"
        elif score >= 80:
            grade = "B+"
            grade_label = "Very Good"
        elif score >= 70:
            grade = "B"
            grade_label = "Good"
        elif score >= 60:
            grade = "C"
            grade_label = "Fair"
        else:
            grade = "D"
            grade_label = "Needs Improvement"

        return {
            'score': score,
            'grade': grade,
            'grade_label': grade_label,
            'issues': issues[:10],  # Top 10 issues
            'suggestions': suggestions[:10],  # Top 10 suggestions
            'strengths': strengths,
            'keyword_density': cls._calculate_keyword_density(resume_data),
            'readability_score': cls._calculate_readability(resume_data),
            'action_verb_count': cls._count_action_verbs(resume_data),
        }

    @classmethod
    def _check_personal_info(cls, info: PersonalInfo) -> Tuple[int, List[str]]:
        score = 0
        issues = []

        if info.full_name:
            score += 5
        else:
            issues.append("Missing name")

        if info.email:
            score += 5
            if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', info.email):
                issues.append("Invalid email format")
                score -= 2
        else:
            issues.append("Missing email address")

        if info.phone:
            score += 4
        else:
            issues.append("Missing phone number")

        if info.location:
            score += 3
        else:
            issues.append("Missing location - some employers filter by location")

        if info.linkedin_url:
            score += 2

        if info.headline:
            score += 1

        return min(20, score), issues

    @classmethod
    def _check_summary(cls, summary: str) -> Tuple[int, List[str], List[str]]:
        score = 0
        issues = []
        suggestions = []

        word_count = len(summary.split())

        if 50 <= word_count <= 200:
            score += 8
        elif word_count < 50:
            issues.append(f"Summary too short ({word_count} words) - aim for 50-200 words")
            score += 3
        else:
            issues.append(f"Summary too long ({word_count} words) - keep it under 200 words")
            score += 5

        # Check for first-person pronouns (should avoid in ATS)
        if re.search(r'\bI\b|\bme\b|\bmy\b', summary, re.IGNORECASE):
            suggestions.append("Consider removing first-person pronouns for ATS compatibility")
            score += 3
        else:
            score += 5

        # Check for action verbs
        summary_lower = summary.lower()
        action_count = sum(1 for verb in cls.ACTION_VERBS if verb in summary_lower)
        if action_count >= 2:
            score += 2
        else:
            suggestions.append("Include more action verbs in your summary")

        return min(15, score), issues, suggestions

    @classmethod
    def _check_experience(cls, experiences: List[ExperienceEntry]) -> Tuple[int, List[str], List[str]]:
        score = 0
        issues = []
        suggestions = []

        if len(experiences) >= 2:
            score += 5
        elif len(experiences) == 1:
            score += 3

        for i, exp in enumerate(experiences):
            exp_issues = []

            if not exp.job_title:
                exp_issues.append(f"Experience #{i+1}: Missing job title")

            if not exp.company:
                exp_issues.append(f"Experience #{i+1}: Missing company name")

            if not exp.description and not exp.achievements:
                exp_issues.append(f"Experience #{i+1}: Add description or achievements")

            # Check for quantifiable achievements
            desc = (exp.description or '') + ' '.join(exp.achievements or [])
            if desc:
                if re.search(r'\d+%|\$[\d,]+|\d+ (million|thousand|people|users|clients)', desc, re.IGNORECASE):
                    score += 3
                else:
                    suggestions.append(f"Add quantifiable achievements to {exp.job_title or 'experience'}")

                # Check for action verbs
                desc_lower = desc.lower()
                action_count = sum(1 for verb in cls.ACTION_VERBS if verb in desc_lower)
                if action_count >= 2:
                    score += 2

            issues.extend(exp_issues)

        return min(30, score), issues, suggestions

    @classmethod
    def _check_education(cls, education: List[EducationEntry]) -> Tuple[int, List[str]]:
        score = 0
        issues = []

        if education:
            score += 5

            for edu in education:
                if edu.institution:
                    score += 3
                else:
                    issues.append("Education entry missing institution name")

                if edu.degree:
                    score += 3
                else:
                    issues.append("Education entry missing degree")

                if edu.field_of_study:
                    score += 2

                if edu.end_date or edu.is_current:
                    score += 2

        return min(15, score), issues

    @classmethod
    def _calculate_keyword_density(cls, resume_data: ResumeData) -> Dict[str, int]:
        """Calculate frequency of important keywords."""
        text = cls._get_all_text(resume_data)
        words = re.findall(r'\b\w+\b', text.lower())

        # Count skill-related words
        skill_names = [s.name.lower() for s in resume_data.skills]
        keyword_counts = {}

        for skill in skill_names:
            count = words.count(skill.lower())
            if count > 0:
                keyword_counts[skill] = count

        return keyword_counts

    @classmethod
    def _calculate_readability(cls, resume_data: ResumeData) -> int:
        """Calculate readability score (0-100)."""
        text = cls._get_all_text(resume_data)

        if not text:
            return 0

        sentences = re.split(r'[.!?]+', text)
        words = re.findall(r'\b\w+\b', text)

        if not words or not sentences:
            return 50

        avg_sentence_length = len(words) / len(sentences)

        # Ideal sentence length is 15-20 words
        if 15 <= avg_sentence_length <= 20:
            return 90
        elif 10 <= avg_sentence_length <= 25:
            return 75
        else:
            return 50

    @classmethod
    def _count_action_verbs(cls, resume_data: ResumeData) -> int:
        """Count action verbs in the resume."""
        text = cls._get_all_text(resume_data).lower()
        return sum(1 for verb in cls.ACTION_VERBS if verb in text)

    @classmethod
    def _get_all_text(cls, resume_data: ResumeData) -> str:
        """Extract all text from resume."""
        parts = [resume_data.summary or '']

        for exp in resume_data.experience:
            parts.append(exp.description or '')
            parts.extend(exp.achievements or [])

        for edu in resume_data.education:
            parts.extend(edu.achievements or [])

        return ' '.join(parts)


class ContentSuggestionEngine:
    """
    AI-powered content suggestion engine.
    Provides smart suggestions for resume content.
    """

    # Summary templates by role category
    SUMMARY_TEMPLATES = {
        'software': [
            "Results-driven {title} with {years}+ years of experience in {skills}. Proven track record of {achievement}. Passionate about {passion}.",
            "Innovative {title} specializing in {skills}. Successfully {achievement}. Seeking to leverage expertise in {goal}.",
        ],
        'marketing': [
            "Creative {title} with {years}+ years driving brand growth and customer engagement. Expert in {skills}. Achieved {achievement}.",
            "Strategic {title} combining analytical skills with creative vision. Specialized in {skills}. {achievement}.",
        ],
        'management': [
            "Dynamic {title} with {years}+ years leading high-performing teams. Expertise in {skills}. Delivered {achievement}.",
            "Accomplished {title} with proven leadership in {skills}. Track record of {achievement}. Committed to {goal}.",
        ],
        'general': [
            "Dedicated {title} with {years}+ years of experience. Skilled in {skills}. Notable achievement: {achievement}.",
            "Motivated {title} bringing expertise in {skills}. Demonstrated ability to {achievement}.",
        ],
    }

    # Achievement templates
    ACHIEVEMENT_TEMPLATES = [
        "Increased {metric} by {percent}% through {action}",
        "Reduced {metric} by {percent}% by implementing {action}",
        "Led team of {number} to deliver {project} {timeframe}",
        "Generated ${amount} in {metric} through {action}",
        "Improved {metric} from {old} to {new}",
        "Streamlined {process} resulting in {percent}% efficiency gain",
        "Managed {amount} budget for {project}",
        "Trained and mentored {number} {role}",
        "Launched {product/feature} reaching {number} users",
    ]

    # Skill suggestions by category
    SKILL_SUGGESTIONS = {
        'software_engineering': [
            'Python', 'JavaScript', 'TypeScript', 'React', 'Node.js', 'Django',
            'AWS', 'Docker', 'Kubernetes', 'Git', 'CI/CD', 'Agile', 'REST APIs',
            'PostgreSQL', 'MongoDB', 'Redis', 'GraphQL', 'Microservices'
        ],
        'data_science': [
            'Python', 'R', 'SQL', 'Machine Learning', 'Deep Learning', 'TensorFlow',
            'PyTorch', 'Pandas', 'NumPy', 'Scikit-learn', 'Data Visualization',
            'Statistical Analysis', 'A/B Testing', 'NLP', 'Computer Vision'
        ],
        'marketing': [
            'Digital Marketing', 'SEO', 'SEM', 'Google Analytics', 'Social Media Marketing',
            'Content Strategy', 'Email Marketing', 'Marketing Automation', 'CRM',
            'Brand Management', 'Market Research', 'Campaign Management'
        ],
        'project_management': [
            'Agile', 'Scrum', 'Kanban', 'JIRA', 'Confluence', 'Project Planning',
            'Risk Management', 'Stakeholder Management', 'Budget Management',
            'Team Leadership', 'Resource Allocation', 'PMP', 'Prince2'
        ],
        'design': [
            'UI/UX Design', 'Figma', 'Sketch', 'Adobe XD', 'Photoshop', 'Illustrator',
            'Wireframing', 'Prototyping', 'User Research', 'Design Systems',
            'Responsive Design', 'Motion Design', 'Accessibility'
        ],
    }

    @classmethod
    def suggest_summary(cls, title: str, skills: List[str], years: int = 0) -> List[str]:
        """Generate summary suggestions based on role and skills."""
        suggestions = []

        # Determine category
        title_lower = title.lower()
        if any(w in title_lower for w in ['software', 'developer', 'engineer', 'programmer']):
            category = 'software'
        elif any(w in title_lower for w in ['marketing', 'brand', 'content']):
            category = 'marketing'
        elif any(w in title_lower for w in ['manager', 'director', 'lead', 'head']):
            category = 'management'
        else:
            category = 'general'

        templates = cls.SUMMARY_TEMPLATES.get(category, cls.SUMMARY_TEMPLATES['general'])

        skills_text = ', '.join(skills[:4]) if skills else 'various technologies'
        years_text = str(years) if years else '5'

        for template in templates:
            suggestion = template.format(
                title=title or 'Professional',
                years=years_text,
                skills=skills_text,
                achievement='delivering high-impact results',
                passion='building innovative solutions',
                goal='driving organizational success',
            )
            suggestions.append(suggestion)

        return suggestions

    @classmethod
    def suggest_achievements(cls, job_title: str, industry: str = '') -> List[str]:
        """Suggest achievement bullet points."""
        suggestions = []

        for template in cls.ACHIEVEMENT_TEMPLATES[:5]:
            suggestion = template.format(
                metric='revenue/productivity/efficiency',
                percent='XX',
                action='strategic initiative',
                number='X',
                project='key project',
                timeframe='on time and under budget',
                amount='XX,XXX',
                old='baseline',
                new='improved state',
                process='key process',
                role='team members',
            )
            suggestions.append(f"• {suggestion}")

        return suggestions

    @classmethod
    def suggest_skills(cls, job_title: str, current_skills: List[str] = None) -> List[str]:
        """Suggest relevant skills based on job title."""
        current_skills = current_skills or []
        current_lower = [s.lower() for s in current_skills]

        # Determine category
        title_lower = job_title.lower()

        suggested = []

        for category, skills in cls.SKILL_SUGGESTIONS.items():
            if any(keyword in title_lower for keyword in category.split('_')):
                for skill in skills:
                    if skill.lower() not in current_lower:
                        suggested.append(skill)

        # If no specific category match, suggest general skills
        if not suggested:
            all_skills = []
            for skills in cls.SKILL_SUGGESTIONS.values():
                all_skills.extend(skills)
            for skill in all_skills[:20]:
                if skill.lower() not in current_lower:
                    suggested.append(skill)

        return suggested[:15]

    @classmethod
    def improve_bullet_point(cls, text: str) -> str:
        """Improve a bullet point with better phrasing."""
        # Remove weak phrases
        improved = text

        weak_phrases = [
            ('responsible for', 'Led'),
            ('duties included', 'Executed'),
            ('worked on', 'Developed'),
            ('helped with', 'Contributed to'),
            ('was involved in', 'Participated in'),
        ]

        for weak, strong in weak_phrases:
            improved = re.sub(weak, strong, improved, flags=re.IGNORECASE)

        # Ensure starts with action verb
        if improved and improved[0].islower():
            improved = improved[0].upper() + improved[1:]

        return improved


class ResumeBuilder:
    """
    Main resume builder class.
    Orchestrates resume creation, editing, and export.
    """

    def __init__(self, user=None):
        self.user = user
        self.resume_data = ResumeData()
        self.ats_optimizer = ATSOptimizer()
        self.suggestion_engine = ContentSuggestionEngine()

    def load_from_profile(self, profile) -> 'ResumeBuilder':
        """Load resume data from user profile."""
        from profiles.models import Education, WorkExperience, TalentSkill, Certification

        # Personal info
        self.resume_data.personal_info = PersonalInfo(
            first_name=self.user.first_name if self.user else '',
            last_name=self.user.last_name if self.user else '',
            email=self.user.email if self.user else '',
            phone=getattr(profile, 'phone_number', '') or '',
            location=self._build_location(profile),
            headline=getattr(profile, 'headline', '') or '',
            linkedin_url=getattr(profile, 'linkedin_url', '') or '',
            github_url=getattr(profile, 'github_url', '') or '',
            portfolio_url=getattr(profile, 'portfolio_url', '') or getattr(profile, 'website', '') or '',
        )

        # Summary
        self.resume_data.summary = getattr(profile, 'bio', '') or ''

        # Experience
        experiences = WorkExperience.objects.filter(profile=profile).order_by('-end_date', '-start_date')
        self.resume_data.experience = [
            ExperienceEntry(
                id=str(exp.id),
                job_title=exp.job_title or '',
                company=exp.company or '',
                location=exp.location or '',
                start_date=exp.start_date.strftime('%Y-%m') if exp.start_date else '',
                end_date=exp.end_date.strftime('%Y-%m') if exp.end_date else '',
                is_current=exp.is_current,
                description=exp.description or '',
                achievements=self._parse_achievements(exp.description),
            )
            for exp in experiences
        ]

        # Education
        education = Education.objects.filter(profile=profile).order_by('-end_date', '-start_date')
        self.resume_data.education = [
            EducationEntry(
                id=str(edu.id),
                institution=edu.institution or '',
                degree=edu.degree or '',
                field_of_study=edu.field_of_study or '',
                start_date=edu.start_date.strftime('%Y-%m') if edu.start_date else '',
                end_date=edu.end_date.strftime('%Y-%m') if edu.end_date else '',
                is_current=edu.is_current,
                gpa=edu.grade or '',
            )
            for edu in education
        ]

        # Skills
        skills = TalentSkill.objects.filter(profile=profile).select_related('skill')
        self.resume_data.skills = [
            SkillEntry(
                name=ts.skill.name,
                level=ts.level or 'intermediate',
                years=ts.years_of_experience or 0,
            )
            for ts in skills
        ]

        # Certifications
        certifications = Certification.objects.filter(profile=profile).order_by('-issue_date')
        self.resume_data.certifications = [
            CertificationEntry(
                id=str(cert.id),
                name=cert.name or '',
                issuer=cert.issuing_organization or '',
                issue_date=cert.issue_date.strftime('%Y-%m') if cert.issue_date else '',
                expiry_date=cert.expiry_date.strftime('%Y-%m') if cert.expiry_date else '',
                credential_id=cert.credential_id or '',
                credential_url=cert.credential_url or '',
            )
            for cert in certifications
        ]

        return self

    def _build_location(self, profile) -> str:
        """Build location string from profile."""
        parts = []
        if getattr(profile, 'city', None):
            parts.append(profile.city)
        if getattr(profile, 'state_province', None):
            parts.append(profile.state_province)
        if getattr(profile, 'country', None):
            parts.append(profile.country)
        return ', '.join(parts)

    def _parse_achievements(self, description: str) -> List[str]:
        """Parse bullet points from description."""
        if not description:
            return []

        # Split by common bullet patterns
        lines = re.split(r'[\n•\-\*]', description)
        achievements = [line.strip() for line in lines if line.strip() and len(line.strip()) > 10]
        return achievements[:5]  # Max 5 achievements

    def get_ats_score(self) -> Dict[str, Any]:
        """Get ATS optimization score and feedback."""
        return self.ats_optimizer.analyze(self.resume_data)

    def get_suggestions(self) -> Dict[str, Any]:
        """Get content suggestions for improving the resume."""
        suggestions = {}

        # Summary suggestions
        if not self.resume_data.summary or len(self.resume_data.summary) < 50:
            title = self.resume_data.personal_info.headline or ''
            skills = [s.name for s in self.resume_data.skills[:5]]
            suggestions['summary'] = self.suggestion_engine.suggest_summary(title, skills)

        # Achievement suggestions for experience
        if self.resume_data.experience:
            suggestions['achievements'] = self.suggestion_engine.suggest_achievements(
                self.resume_data.experience[0].job_title
            )

        # Skill suggestions
        current_skills = [s.name for s in self.resume_data.skills]
        title = self.resume_data.personal_info.headline or (
            self.resume_data.experience[0].job_title if self.resume_data.experience else ''
        )
        suggestions['skills'] = self.suggestion_engine.suggest_skills(title, current_skills)

        return suggestions

    def to_dict(self) -> Dict[str, Any]:
        """Convert resume data to dictionary."""
        return {
            'personal_info': asdict(self.resume_data.personal_info),
            'summary': self.resume_data.summary,
            'experience': [asdict(e) for e in self.resume_data.experience],
            'education': [asdict(e) for e in self.resume_data.education],
            'skills': [asdict(s) for s in self.resume_data.skills],
            'certifications': [asdict(c) for c in self.resume_data.certifications],
            'projects': [asdict(p) for p in self.resume_data.projects],
            'languages': self.resume_data.languages,
            'template': self.resume_data.template,
            'section_order': self.resume_data.section_order,
            'color_scheme': self.resume_data.color_scheme,
            'font_family': self.resume_data.font_family,
        }

    def from_dict(self, data: Dict[str, Any]) -> 'ResumeBuilder':
        """Load resume data from dictionary."""
        if 'personal_info' in data:
            self.resume_data.personal_info = PersonalInfo(**data['personal_info'])

        if 'summary' in data:
            self.resume_data.summary = data['summary']

        if 'experience' in data:
            self.resume_data.experience = [ExperienceEntry(**e) for e in data['experience']]

        if 'education' in data:
            self.resume_data.education = [EducationEntry(**e) for e in data['education']]

        if 'skills' in data:
            self.resume_data.skills = [SkillEntry(**s) for s in data['skills']]

        if 'certifications' in data:
            self.resume_data.certifications = [CertificationEntry(**c) for c in data['certifications']]

        if 'projects' in data:
            self.resume_data.projects = [ProjectEntry(**p) for p in data['projects']]

        if 'template' in data:
            self.resume_data.template = data['template']

        if 'section_order' in data:
            self.resume_data.section_order = data['section_order']

        return self

    def update_section(self, section: str, data: Any) -> 'ResumeBuilder':
        """Update a specific section."""
        if section == 'personal_info':
            self.resume_data.personal_info = PersonalInfo(**data) if isinstance(data, dict) else data
        elif section == 'summary':
            self.resume_data.summary = data
        elif section == 'experience':
            self.resume_data.experience = [ExperienceEntry(**e) if isinstance(e, dict) else e for e in data]
        elif section == 'education':
            self.resume_data.education = [EducationEntry(**e) if isinstance(e, dict) else e for e in data]
        elif section == 'skills':
            self.resume_data.skills = [SkillEntry(**s) if isinstance(s, dict) else s for s in data]
        elif section == 'template':
            self.resume_data.template = data
        elif section == 'section_order':
            self.resume_data.section_order = data

        return self


class ResumeExporter:
    """
    Export resume to various formats.
    Supports PDF, DOCX, HTML, and JSON.
    """

    TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'resume_templates')

    @classmethod
    def to_html(cls, resume_data: ResumeData, template: str = 'professional') -> str:
        """Generate HTML resume."""
        # This will be rendered via Django template
        return cls._render_template(resume_data, template)

    @classmethod
    def to_pdf(cls, resume_data: ResumeData, template: str = 'professional') -> bytes:
        """Generate PDF resume using WeasyPrint or reportlab."""
        try:
            from weasyprint import HTML, CSS

            html_content = cls.to_html(resume_data, template)
            css = cls._get_pdf_css(template)

            html = HTML(string=html_content)
            pdf_bytes = html.write_pdf(stylesheets=[CSS(string=css)])

            return pdf_bytes
        except ImportError:
            # Fallback to reportlab if weasyprint not available
            return cls._to_pdf_reportlab(resume_data, template)

    @classmethod
    def _to_pdf_reportlab(cls, resume_data: ResumeData, template: str) -> bytes:
        """Generate PDF using reportlab as fallback."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch, cm
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4,
                                    leftMargin=0.75*inch, rightMargin=0.75*inch,
                                    topMargin=0.5*inch, bottomMargin=0.5*inch)

            styles = getSampleStyleSheet()

            # Custom styles
            styles.add(ParagraphStyle(
                'Name',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#1a365d'),
                spaceAfter=6,
                alignment=TA_CENTER,
            ))

            styles.add(ParagraphStyle(
                'Headline',
                parent=styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor('#4a5568'),
                alignment=TA_CENTER,
                spaceAfter=12,
            ))

            styles.add(ParagraphStyle(
                'SectionTitle',
                parent=styles['Heading2'],
                fontSize=14,
                textColor=colors.HexColor('#2d3748'),
                spaceBefore=16,
                spaceAfter=8,
                borderWidth=1,
                borderColor=colors.HexColor('#e2e8f0'),
                borderPadding=4,
            ))

            styles.add(ParagraphStyle(
                'JobTitle',
                parent=styles['Normal'],
                fontSize=11,
                textColor=colors.HexColor('#1a365d'),
                fontName='Helvetica-Bold',
            ))

            styles.add(ParagraphStyle(
                'Company',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#4a5568'),
            ))

            styles.add(ParagraphStyle(
                'BodyText',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#4a5568'),
                alignment=TA_JUSTIFY,
                spaceAfter=6,
            ))

            styles.add(ParagraphStyle(
                'Contact',
                parent=styles['Normal'],
                fontSize=9,
                textColor=colors.HexColor('#718096'),
                alignment=TA_CENTER,
            ))

            elements = []
            info = resume_data.personal_info

            # Header
            elements.append(Paragraph(info.full_name, styles['Name']))

            if info.headline:
                elements.append(Paragraph(info.headline, styles['Headline']))

            # Contact info
            contact_parts = []
            if info.email:
                contact_parts.append(info.email)
            if info.phone:
                contact_parts.append(info.phone)
            if info.location:
                contact_parts.append(info.location)
            if info.linkedin_url:
                contact_parts.append('LinkedIn')

            if contact_parts:
                elements.append(Paragraph(' | '.join(contact_parts), styles['Contact']))

            elements.append(Spacer(1, 12))

            # Summary
            if resume_data.summary:
                elements.append(Paragraph('PROFESSIONAL SUMMARY', styles['SectionTitle']))
                elements.append(Paragraph(resume_data.summary, styles['BodyText']))

            # Experience
            if resume_data.experience:
                elements.append(Paragraph('WORK EXPERIENCE', styles['SectionTitle']))

                for exp in resume_data.experience:
                    date_str = f"{exp.start_date} - {'Present' if exp.is_current else exp.end_date}"

                    elements.append(Paragraph(f"<b>{exp.job_title}</b>", styles['JobTitle']))
                    elements.append(Paragraph(f"{exp.company} | {date_str}", styles['Company']))

                    if exp.description:
                        elements.append(Paragraph(exp.description, styles['BodyText']))

                    if exp.achievements:
                        for achievement in exp.achievements:
                            elements.append(Paragraph(f"• {achievement}", styles['BodyText']))

                    elements.append(Spacer(1, 8))

            # Education
            if resume_data.education:
                elements.append(Paragraph('EDUCATION', styles['SectionTitle']))

                for edu in resume_data.education:
                    degree_text = edu.degree
                    if edu.field_of_study:
                        degree_text += f" in {edu.field_of_study}"

                    elements.append(Paragraph(f"<b>{degree_text}</b>", styles['JobTitle']))

                    date_str = f"{edu.start_date} - {'Present' if edu.is_current else edu.end_date}"
                    elements.append(Paragraph(f"{edu.institution} | {date_str}", styles['Company']))

                    if edu.gpa:
                        elements.append(Paragraph(f"GPA: {edu.gpa}", styles['BodyText']))

                    elements.append(Spacer(1, 6))

            # Skills
            if resume_data.skills:
                elements.append(Paragraph('SKILLS', styles['SectionTitle']))

                skill_names = [s.name for s in resume_data.skills]
                skills_text = ' • '.join(skill_names)
                elements.append(Paragraph(skills_text, styles['BodyText']))

            # Certifications
            if resume_data.certifications:
                elements.append(Paragraph('CERTIFICATIONS', styles['SectionTitle']))

                for cert in resume_data.certifications:
                    cert_text = f"<b>{cert.name}</b> - {cert.issuer}"
                    if cert.issue_date:
                        cert_text += f" ({cert.issue_date})"
                    elements.append(Paragraph(cert_text, styles['BodyText']))

            # Build PDF
            doc.build(elements)

            buffer.seek(0)
            return buffer.getvalue()

        except ImportError as e:
            logger.error(f"PDF generation failed: {e}")
            raise ValueError("PDF generation not available. Install reportlab or weasyprint.")

    @classmethod
    def _render_template(cls, resume_data: ResumeData, template: str) -> str:
        """Render resume HTML template."""
        info = resume_data.personal_info

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{info.full_name} - Resume</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ 
                    font-family: 'Helvetica Neue', Arial, sans-serif; 
                    color: #333;
                    line-height: 1.5;
                    padding: 40px;
                    max-width: 800px;
                    margin: 0 auto;
                }}
                .header {{ text-align: center; margin-bottom: 24px; }}
                .name {{ font-size: 28px; font-weight: 700; color: #1a365d; }}
                .headline {{ font-size: 14px; color: #4a5568; margin-top: 4px; }}
                .contact {{ font-size: 12px; color: #718096; margin-top: 8px; }}
                .section {{ margin-top: 20px; }}
                .section-title {{ 
                    font-size: 14px; 
                    font-weight: 600; 
                    color: #2d3748;
                    text-transform: uppercase;
                    border-bottom: 2px solid #e2e8f0;
                    padding-bottom: 4px;
                    margin-bottom: 12px;
                }}
                .entry {{ margin-bottom: 16px; }}
                .entry-header {{ display: flex; justify-content: space-between; }}
                .entry-title {{ font-weight: 600; color: #1a365d; }}
                .entry-subtitle {{ color: #4a5568; }}
                .entry-date {{ color: #718096; font-size: 12px; }}
                .entry-description {{ margin-top: 6px; color: #4a5568; font-size: 13px; }}
                .skills-list {{ display: flex; flex-wrap: wrap; gap: 8px; }}
                .skill-tag {{ 
                    background: #edf2f7; 
                    padding: 4px 12px; 
                    border-radius: 4px; 
                    font-size: 12px;
                    color: #4a5568;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="name">{info.full_name}</div>
                <div class="headline">{info.headline}</div>
                <div class="contact">
                    {info.email} | {info.phone} | {info.location}
                </div>
            </div>
        """

        # Summary
        if resume_data.summary:
            html += f"""
            <div class="section">
                <div class="section-title">Professional Summary</div>
                <p style="color: #4a5568; font-size: 13px;">{resume_data.summary}</p>
            </div>
            """

        # Experience
        if resume_data.experience:
            html += """<div class="section"><div class="section-title">Work Experience</div>"""
            for exp in resume_data.experience:
                date_range = f"{exp.start_date} - {'Present' if exp.is_current else exp.end_date}"
                html += f"""
                <div class="entry">
                    <div class="entry-header">
                        <div>
                            <div class="entry-title">{exp.job_title}</div>
                            <div class="entry-subtitle">{exp.company}</div>
                        </div>
                        <div class="entry-date">{date_range}</div>
                    </div>
                    <div class="entry-description">{exp.description}</div>
                </div>
                """
            html += "</div>"

        # Education
        if resume_data.education:
            html += """<div class="section"><div class="section-title">Education</div>"""
            for edu in resume_data.education:
                date_range = f"{edu.start_date} - {'Present' if edu.is_current else edu.end_date}"
                degree = f"{edu.degree}"
                if edu.field_of_study:
                    degree += f" in {edu.field_of_study}"
                html += f"""
                <div class="entry">
                    <div class="entry-header">
                        <div>
                            <div class="entry-title">{degree}</div>
                            <div class="entry-subtitle">{edu.institution}</div>
                        </div>
                        <div class="entry-date">{date_range}</div>
                    </div>
                </div>
                """
            html += "</div>"

        # Skills
        if resume_data.skills:
            html += """<div class="section"><div class="section-title">Skills</div><div class="skills-list">"""
            for skill in resume_data.skills:
                html += f'<span class="skill-tag">{skill.name}</span>'
            html += "</div></div>"

        html += """
        </body>
        </html>
        """

        return html

    @classmethod
    def _get_pdf_css(cls, template: str) -> str:
        """Get CSS for PDF generation."""
        return """
            @page { size: A4; margin: 1cm; }
            body { font-family: 'Helvetica Neue', Arial, sans-serif; }
        """

    @classmethod
    def to_json(cls, resume_data: ResumeData) -> str:
        """Export resume as JSON."""
        builder = ResumeBuilder()
        builder.resume_data = resume_data
        return json.dumps(builder.to_dict(), indent=2)


# Convenience functions
def create_resume_builder(user=None) -> ResumeBuilder:
    """Create a new ResumeBuilder instance."""
    return ResumeBuilder(user)


def analyze_resume(resume_data: ResumeData) -> Dict[str, Any]:
    """Analyze resume for ATS optimization."""
    return ATSOptimizer.analyze(resume_data)


def export_resume_pdf(resume_data: ResumeData, template: str = 'professional') -> bytes:
    """Export resume to PDF."""
    return ResumeExporter.to_pdf(resume_data, template)


def export_resume_html(resume_data: ResumeData, template: str = 'professional') -> str:
    """Export resume to HTML."""
    return ResumeExporter.to_html(resume_data, template)

