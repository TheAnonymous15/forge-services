"""
ForgeForth - Email Service
==========================
Handles all email communications with unified compact templates.
"""

import logging
from datetime import datetime, timezone as dt_timezone, timedelta
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

try:
    import pytz
    HAS_PYTZ = True
except ImportError:
    HAS_PYTZ = False

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails with unified compact templates."""

    def __init__(self):
        self.from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'mailer@forgeforthafrica.com')
        self.contact_email = getattr(settings, 'CONTACT_EMAIL', 'info@forgeforthafrica.com')

    def _get_email_template(self, icon, title, subtitle, body_content, accent_color="38bdf8"):
        """
        Generate unified email template with consistent header and footer.
        Only the body_content differs between email types.
        Theme: Modern compact glassmorphism with dark gradient background.
        """

        return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Roboto,-apple-system,BlinkMacSystemFont,sans-serif;background:#08080d;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#08080d;padding:32px 16px;">
        <tr>
            <td align="center">
                <table width="400" cellpadding="0" cellspacing="0" style="max-width:400px;width:100%;">
                    <tr>
                        <td>
                            <!-- MAIN CARD -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(145deg,rgba(25,25,40,0.98),rgba(18,18,28,0.99));border-radius:16px;overflow:hidden;box-shadow:0 20px 40px rgba(0,0,0,0.4),0 0 0 1px rgba(255,255,255,0.04);">
                                
                                <!-- Gradient accent line -->
                                <tr>
                                    <td style="padding:0;">
                                        <div style="height:2px;background:linear-gradient(90deg,#a855f7,#ec4899,#f97316);"></div>
                                    </td>
                                </tr>
                                
                                <!-- Header -->
                                <tr>
                                    <td style="padding:20px 20px 14px;">
                                        <table width="100%" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td width="42" style="vertical-align:middle;">
                                                    <div style="width:38px;height:38px;background:linear-gradient(135deg,#a855f7,#ec4899);border-radius:10px;text-align:center;line-height:38px;font-size:18px;">{icon}</div>
                                                </td>
                                                <td style="vertical-align:middle;padding-left:12px;">
                                                    <p style="color:#fff;margin:0;font-size:15px;font-weight:600;letter-spacing:-0.2px;">{title}</p>
                                                    <p style="color:rgba(255,255,255,0.45);margin:2px 0 0;font-size:11px;">{subtitle}</p>
                                                </td>
                                                <td width="28" style="vertical-align:middle;text-align:right;">
                                                    <div style="width:26px;height:26px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);border-radius:7px;text-align:center;line-height:24px;font-size:11px;font-weight:700;color:rgba(255,255,255,0.5);">FF</div>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                                
                                <!-- Divider -->
                                <tr>
                                    <td style="padding:0 20px;">
                                        <div style="height:1px;background:rgba(255,255,255,0.06);"></div>
                                    </td>
                                </tr>
                                
                                <!-- BODY -->
                                <tr>
                                    <td style="padding:16px 20px 20px;">
                                        {body_content}
                                    </td>
                                </tr>
                                
                                <!-- Footer -->
                                <tr>
                                    <td style="padding:0 20px 16px;">
                                        <p style="color:rgba(255,255,255,0.25);margin:0;font-size:10px;text-align:center;">
                                            <span style="color:rgba(168,85,247,0.6);">●</span> ForgeForth · forgeforthafrica.com
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>'''

    # ==================== CONTACT FORM ====================

    def send_contact_form_email(self, name, email, subject, message, inquiry_type=None, company=None, phone=None):
        """Send contact form emails to team and user."""
        try:
            self._send_contact_notification(name, email, subject, message, inquiry_type, company, phone)
            self._send_contact_confirmation(name, email, message)
            return True, "Email sent successfully"
        except Exception as e:
            logger.error(f"Error sending contact form email: {e}")
            return False, str(e)

    def _send_contact_notification(self, name, email, subject, message, inquiry_type=None, company=None, phone=None):
        """Send notification to ForgeForth team."""

        body = f'''
        <!-- Greeting -->
        <p style="color:rgba(255,255,255,0.8);font-size:13px;line-height:1.6;margin:0 0 6px;">
            Greetings ForgeForth Team,
        </p>
        <p style="color:rgba(255,255,255,0.65);font-size:13px;line-height:1.6;margin:0 0 6px;">
            You have received a new message.
        </p>
        <p style="color:rgba(255,255,255,0.5);font-size:12px;margin:0 0 14px;">
            See details below:
        </p>
        
        <!-- Contact Info Card -->
        <table width="100%" cellpadding="0" cellspacing="0" style="background:rgba(255,255,255,0.03);border-radius:12px;border:1px solid rgba(255,255,255,0.06);margin-bottom:16px;">
            <tr>
                <td style="padding:14px 16px;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                            <td width="50%" style="vertical-align:middle;">
                                <p style="color:rgba(255,255,255,0.4);font-size:9px;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 3px;">Name</p>
                                <p style="color:#a855f7;font-size:14px;font-weight:600;margin:0;">{name}</p>
                            </td>
                            <td width="50%" style="vertical-align:middle;text-align:right;">
                                <p style="color:rgba(255,255,255,0.4);font-size:9px;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 3px;">Email</p>
                                <a href="mailto:{email}" style="color:#ec4899;font-size:14px;font-weight:600;text-decoration:none;">{email}</a>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            ''' + (f'''
            <tr>
                <td style="padding:0 16px;">
                    <div style="height:1px;background:rgba(255,255,255,0.06);"></div>
                </td>
            </tr>
            <tr>
                <td style="padding:12px 16px;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                            <td width="50%" style="vertical-align:middle;">
                                <p style="color:rgba(255,255,255,0.4);font-size:9px;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 3px;">Phone</p>
                                <p style="color:#10b981;font-size:13px;font-weight:500;margin:0;">📱 {phone}</p>
                            </td>
                            ''' + (f'''
                            <td width="50%" style="vertical-align:middle;text-align:right;">
                                <p style="color:rgba(255,255,255,0.4);font-size:9px;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 3px;">Company</p>
                                <p style="color:rgba(255,255,255,0.7);font-size:13px;font-weight:500;margin:0;">🏢 {company}</p>
                            </td>
                            ''' if company else '') + '''
                        </tr>
                    </table>
                </td>
            </tr>
            ''' if phone else '') + (f'''
            <tr>
                <td style="padding:0 16px;">
                    <div style="height:1px;background:rgba(255,255,255,0.06);"></div>
                </td>
            </tr>
            <tr>
                <td style="padding:12px 16px;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                            <td width="50%" style="vertical-align:middle;">
                                <p style="color:rgba(255,255,255,0.4);font-size:9px;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 3px;">Inquiry Type</p>
                                <p style="color:#f97316;font-size:13px;font-weight:500;margin:0;">{inquiry_type}</p>
                            </td>
                            <td width="50%" style="vertical-align:middle;text-align:right;">
                                <p style="color:rgba(255,255,255,0.4);font-size:9px;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 3px;">Subject</p>
                                <p style="color:rgba(255,255,255,0.7);font-size:13px;font-weight:500;margin:0;">{subject or "No subject"}</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            ''' if inquiry_type else f'''
            <tr>
                <td style="padding:0 16px;">
                    <div style="height:1px;background:rgba(255,255,255,0.06);"></div>
                </td>
            </tr>
            <tr>
                <td style="padding:12px 16px;">
                    <p style="color:rgba(255,255,255,0.4);font-size:9px;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 3px;">Subject</p>
                    <p style="color:rgba(255,255,255,0.7);font-size:13px;font-weight:500;margin:0;">{subject or "No subject"}</p>
                </td>
            </tr>
            ''') + '''
        </table>
        
        <!-- Message Box -->
        <table width="100%" cellpadding="0" cellspacing="0" style="background:rgba(168,85,247,0.06);border-radius:12px;border-left:3px solid #a855f7;margin-bottom:14px;">
            <tr>
                <td style="padding:14px 16px;">
                    <p style="color:rgba(255,255,255,0.4);font-size:9px;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 8px;">Message</p>
                    <p style="color:rgba(255,255,255,0.85);font-size:13px;line-height:1.6;margin:0;white-space:pre-wrap;">''' + message + '''</p>
                </td>
            </tr>
        </table>
        
        <!-- Reply Button -->
        <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
                <td align="center">
                    <a href="mailto:''' + email + '''" style="display:inline-block;background:linear-gradient(135deg,#a855f7,#ec4899);color:#fff;font-size:13px;font-weight:600;text-decoration:none;padding:12px 28px;border-radius:10px;box-shadow:0 4px 12px rgba(168,85,247,0.3);">
                        ✉️ Reply to ''' + name.split()[0] + '''
                    </a>
                </td>
            </tr>
        </table>
        '''

        html = self._get_email_template("💬", "New Message", f"From {name}", body)

        msg = EmailMultiAlternatives(
            subject=f"[Contact] {subject or 'New Message'}",
            body=f"From: {name} ({email})\n\n{message}",
            from_email=self.from_email,
            to=[self.contact_email],
            reply_to=[email]
        )
        msg.attach_alternative(html, "text/html")
        msg.send(fail_silently=False)
        logger.info(f"Contact notification sent to {self.contact_email}")

    def _send_contact_confirmation(self, name, email, message):
        """Send confirmation to user."""

        body = f'''
        <p style="color:rgba(255,255,255,0.9);font-size:14px;line-height:1.6;margin:0 0 16px;">
            Hi <span style="color:#a855f7;font-weight:600;">{name}</span>, thanks for reaching out!
        </p>
        <p style="color:rgba(255,255,255,0.6);font-size:13px;line-height:1.5;margin:0 0 16px;">
            We'll get back to you within <span style="color:#ec4899;font-weight:500;">24-48 hours</span>.
        </p>
        <table width="100%" cellpadding="0" cellspacing="0" style="background:rgba(255,255,255,0.04);border-radius:10px;border-left:3px solid rgba(168,85,247,0.5);margin-bottom:16px;">
            <tr><td style="padding:12px 14px;">
                <p style="color:rgba(255,255,255,0.45);font-size:10px;text-transform:uppercase;margin:0 0 6px;">Your message</p>
                <p style="color:rgba(255,255,255,0.7);font-size:12px;line-height:1.5;margin:0;font-style:italic;">{message[:150]}{"..." if len(message) > 150 else ""}</p>
            </td></tr>
        </table>
        <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
                <td width="33%" style="padding-right:4px;">
                    <a href="mailto:info@forgeforthafrica.com" style="display:block;background:rgba(168,85,247,0.1);border:1px solid rgba(168,85,247,0.25);border-radius:8px;padding:10px 6px;text-align:center;text-decoration:none;">
                        <span style="color:#a855f7;font-size:10px;font-weight:500;">📧 Email Us</span>
                    </a>
                </td>
                <td width="34%" style="padding:0 2px;">
                    <a href="tel:+27692973425" style="display:block;background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.25);border-radius:8px;padding:10px 6px;text-align:center;text-decoration:none;">
                        <span style="color:#10b981;font-size:10px;font-weight:500;">📞 Call Us</span>
                    </a>
                </td>
                <td width="33%" style="padding-left:4px;">
                    <a href="https://wa.me/27692973425" style="display:block;background:rgba(37,211,102,0.1);border:1px solid rgba(37,211,102,0.25);border-radius:8px;padding:10px 6px;text-align:center;text-decoration:none;">
                        <span style="color:#25D366;font-size:10px;font-weight:500;">💬 WhatsApp</span>
                    </a>
                </td>
            </tr>
        </table>
        <p style="color:rgba(255,255,255,0.5);font-size:12px;margin:16px 0 0;">— The ForgeForth Team</p>
        '''

        html = self._get_email_template("✓", "Message Received", "We'll be in touch", body)

        msg = EmailMultiAlternatives(
            subject="Thank you for contacting ForgeForth Africa",
            body=f"Hi {name}, thanks for reaching out! We'll respond within 24-48 hours.",
            from_email=self.from_email,
            to=[email],
            reply_to=[self.contact_email]
        )
        msg.attach_alternative(html, "text/html")
        msg.send(fail_silently=False)
        logger.info(f"Contact confirmation sent to {email}")

    # ==================== CALLBACK REQUEST ====================

    def send_callback_request(self, name, phone, time=None, timezone=None, channel='phone'):
        """Send callback request to team with timezone-aware call timing.

        Args:
            name: Customer name
            phone: Customer phone number
            time: Preferred callback time
            timezone: Customer's timezone (IANA format preferred, e.g., 'Africa/Nairobi')
            channel: Preferred call channel - 'phone' or 'whatsapp'
        """
        try:
            # Default timezone to SAST (South Africa Standard Time)
            tz_display = self._get_timezone_display(timezone)
            tz_offset = self._get_timezone_offset(timezone)

            # Normalize channel
            channel = (channel or 'phone').lower().strip()
            if channel not in ['phone', 'whatsapp']:
                channel = 'phone'

            # Format time display
            call_window_start = None
            call_window_end = None

            if time:
                if isinstance(time, str) and ' - ' in time:
                    time_parts = time.split(' - ')
                    from_time = time_parts[0].strip()
                    to_time = time_parts[1].strip() if len(time_parts) > 1 else ''

                    call_window_start, call_window_end = self._parse_time_range(from_time, to_time)

                    try:
                        hour = int(from_time.split(':')[0])
                        if 'PM' in from_time.upper() and hour != 12:
                            hour += 12
                        elif 'AM' in from_time.upper() and hour == 12:
                            hour = 0
                        if hour < 12:
                            period_label = "Morning"
                            period_icon = "☀️"
                        elif hour < 17:
                            period_label = "Afternoon"
                            period_icon = "🌤️"
                        else:
                            period_label = "Evening"
                            period_icon = "🌙"
                    except:
                        period_label = "Preferred"
                        period_icon = "🕐"

                    time_display = f"{from_time} → {to_time}" if to_time else from_time
                else:
                    try:
                        dt = None
                        if isinstance(time, str):
                            for fmt in ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S']:
                                try:
                                    dt = datetime.strptime(time, fmt)
                                    break
                                except ValueError:
                                    continue
                        else:
                            dt = time

                        if dt:
                            period_label = dt.strftime('%A')
                            period_icon = "📅"
                            time_display = dt.strftime('%I:%M %p').lstrip('0')
                            call_window_start = dt.hour
                            call_window_end = dt.hour + 1
                        else:
                            period_label = "Preferred"
                            period_icon = "🕐"
                            time_display = str(time)
                    except:
                        period_label = "Preferred"
                        period_icon = "🕐"
                        time_display = str(time)
            else:
                period_label = "Flexible"
                period_icon = "✨"
                time_display = "Anytime"

            channel_icon = "📱" if channel == 'phone' else "💬"
            channel_label = "Phone Call" if channel == 'phone' else "WhatsApp"

            body = f'''
            <!-- Greeting Message -->
            <p style="color:rgba(255,255,255,0.8);font-size:13px;line-height:1.6;margin:0 0 6px;">
                Greetings ForgeForth Team,
            </p>
            <p style="color:rgba(255,255,255,0.65);font-size:13px;line-height:1.6;margin:0 0 6px;">
                You have a new callback request.
            </p>
            <p style="color:rgba(255,255,255,0.5);font-size:12px;margin:0 0 14px;">
                See details below:
            </p>
            
            <!-- Compact Info Row -->
            <table width="100%" cellpadding="0" cellspacing="0" style="background:rgba(255,255,255,0.03);border-radius:12px;border:1px solid rgba(255,255,255,0.06);margin-bottom:16px;">
                <tr>
                    <td style="padding:14px 16px;">
                        <table width="100%" cellpadding="0" cellspacing="0">
                            <tr>
                                <td width="50%" style="vertical-align:middle;">
                                    <p style="color:rgba(255,255,255,0.4);font-size:9px;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 3px;">Customer</p>
                                    <p style="color:#a855f7;font-size:14px;font-weight:600;margin:0;">{name if name else '—'}</p>
                                </td>
                                <td width="50%" style="vertical-align:middle;text-align:right;">
                                    <p style="color:rgba(255,255,255,0.4);font-size:9px;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 3px;">Phone</p>
                                    <p style="color:#ec4899;font-size:14px;font-weight:600;margin:0;">{phone if phone else '—'}</p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
                <tr>
                    <td style="padding:0 16px;">
                        <div style="height:1px;background:rgba(255,255,255,0.06);"></div>
                    </td>
                </tr>
                <tr>
                    <td style="padding:12px 16px;">
                        <table width="100%" cellpadding="0" cellspacing="0">
                            <tr>
                                <td width="50%" style="vertical-align:middle;">
                                    <p style="color:rgba(255,255,255,0.4);font-size:9px;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 3px;">Preferred Channel</p>
                                    <p style="color:{'#25D366' if channel == 'whatsapp' else '#10b981'};font-size:13px;font-weight:500;margin:0;">{channel_icon} {channel_label}</p>
                                </td>
                                <td width="50%" style="vertical-align:middle;text-align:right;">
                                    <p style="color:rgba(255,255,255,0.4);font-size:9px;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 3px;">Timezone</p>
                                    <p style="color:rgba(255,255,255,0.6);font-size:13px;font-weight:500;margin:0;">🌍 {tz_display}</p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
                <tr>
                    <td style="padding:0 16px;">
                        <div style="height:1px;background:rgba(255,255,255,0.06);"></div>
                    </td>
                </tr>
                <tr>
                    <td style="padding:12px 16px;">
                        <table width="100%" cellpadding="0" cellspacing="0">
                            <tr>
                                <td width="28" style="vertical-align:middle;">
                                    <span style="font-size:18px;">{period_icon}</span>
                                </td>
                                <td style="vertical-align:middle;padding-left:10px;">
                                    <p style="color:#f97316;font-size:13px;font-weight:500;margin:0;">{period_label} · <span style="color:rgba(255,255,255,0.6);">{time_display}</span></p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
            
            <!-- Smart Call Button -->
            ''' + self._build_smart_call_button(name, phone, call_window_start, call_window_end, tz_offset, tz_display, period_label, channel) + '''
            '''

            html = self._get_email_template("📞", "Callback Request", f"{name} wants a call", body)

            msg = EmailMultiAlternatives(
                subject="[Callback] Call Request",
                body=f"Callback Request\nName: {name}\nPhone: {phone}\nPreferred Time: {time}\nTimezone: {tz_display}\nChannel: {channel}",
                from_email=self.from_email,
                to=[self.contact_email]
            )
            msg.attach_alternative(html, "text/html")
            msg.send(fail_silently=False)

            logger.info(f"Callback request sent for {name} ({phone})")
            return True, "Callback request sent"
        except Exception as e:
            logger.error(f"Error sending callback request: {e}")
            return False, str(e)

    def _get_timezone_display(self, timezone):
        """Get a user-friendly display name for the timezone."""
        if not timezone:
            return "SAST (South Africa)"

        display_names = {
            'Africa/Johannesburg': 'SAST (Johannesburg)',
            'Africa/Nairobi': 'EAT (Nairobi)',
            'Africa/Lagos': 'WAT (Lagos)',
            'Africa/Cairo': 'EET (Cairo)',
            'Europe/London': 'GMT (London)',
            'Europe/Paris': 'CET (Paris)',
            'America/New_York': 'EST (New York)',
            'America/Los_Angeles': 'PST (Los Angeles)',
            'Asia/Dubai': 'GST (Dubai)',
        }

        if timezone in display_names:
            return display_names[timezone]

        offset = self._get_timezone_offset(timezone)
        if offset >= 0:
            return f"UTC+{int(offset)}" if offset == int(offset) else f"UTC+{offset}"
        else:
            return f"UTC{int(offset)}" if offset == int(offset) else f"UTC{offset}"

    def _get_timezone_offset(self, timezone):
        """Get UTC offset for timezone."""
        if not timezone:
            return 2  # Default SAST

        if HAS_PYTZ:
            try:
                tz = pytz.timezone(timezone)
                now = datetime.now(pytz.UTC)
                offset = tz.utcoffset(now).total_seconds() / 3600
                return offset
            except:
                pass

        iana_offsets = {
            'Africa/Johannesburg': 2, 'Africa/Nairobi': 3, 'Africa/Lagos': 1,
            'Africa/Cairo': 2, 'Europe/London': 0, 'Europe/Paris': 1,
            'America/New_York': -5, 'America/Los_Angeles': -8,
            'Asia/Dubai': 4, 'Asia/Tokyo': 9,
        }

        tz_offsets = {
            'SAST': 2, 'EAT': 3, 'WAT': 1, 'CAT': 2,
            'GMT': 0, 'UTC': 0, 'EST': -5, 'PST': -8,
        }

        if timezone in iana_offsets:
            return iana_offsets[timezone]

        return tz_offsets.get(timezone.upper(), 2)

    def _parse_time_range(self, from_time, to_time):
        """Parse time strings to hour values (24h format)."""
        def parse_hour(time_str):
            try:
                time_str = time_str.strip().upper()
                has_am_pm = 'AM' in time_str or 'PM' in time_str

                if has_am_pm:
                    parts = time_str.replace('AM', '').replace('PM', '').strip().split(':')
                    hour = int(parts[0])
                    is_pm = 'PM' in time_str
                    is_am = 'AM' in time_str

                    if is_pm and hour != 12:
                        hour += 12
                    elif is_am and hour == 12:
                        hour = 0
                else:
                    parts = time_str.split(':')
                    hour = int(parts[0])

                return hour
            except:
                return None

        start = parse_hour(from_time)
        end = parse_hour(to_time) if to_time else (start + 3 if start is not None else None)
        return start, end

    def _build_smart_call_button(self, name, phone, window_start, window_end, tz_offset, tz_display, period_label, channel='phone'):
        """Build a smart call button with time awareness."""
        if not phone:
            return ''

        first_name = name.split()[0] if name else "Customer"

        whatsapp_phone = ''.join(c for c in phone if c.isdigit() or c == '+')
        if not whatsapp_phone.startswith('+'):
            whatsapp_phone = '+' + whatsapp_phone

        if channel == 'whatsapp':
            button_gradient = "linear-gradient(135deg,#25D366,#128C7E)"
            button_shadow = "0 4px 12px rgba(37,211,102,0.3)"
            button_icon = "💬"
            button_text = f"Call {first_name} via WhatsApp"
            button_href = f"https://wa.me/{whatsapp_phone.replace('+', '')}"
        else:
            button_gradient = "linear-gradient(135deg,#10b981,#059669)"
            button_shadow = "0 4px 12px rgba(16,185,129,0.3)"
            button_icon = "📞"
            button_text = f"Call {first_name} on Phone"
            button_href = f"tel:{phone}"

        if window_start is None:
            return f'''
            <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                    <td align="center">
                        <a href="{button_href}" style="display:inline-block;background:{button_gradient};color:#fff;font-size:13px;font-weight:600;text-decoration:none;padding:12px 28px;border-radius:10px;box-shadow:{button_shadow};">
                            {button_icon} {button_text}
                        </a>
                    </td>
                </tr>
            </table>
            '''

        now_utc = datetime.now(dt_timezone.utc)
        customer_time = now_utc + timedelta(hours=tz_offset)
        customer_hour = customer_time.hour + customer_time.minute / 60
        customer_time_str = customer_time.strftime('%I:%M %p').lstrip('0')

        is_good_time = window_start <= customer_hour < window_end

        if is_good_time:
            return f'''
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:8px;">
                <tr>
                    <td align="center">
                        <table cellpadding="0" cellspacing="0" style="background-color:#052e16;border-radius:8px;border:2px solid #10b981;">
                            <tr>
                                <td style="padding:8px 14px;">
                                    <p style="color:#34d399;margin:0;font-weight:600;font-size:12px;">✅ Good time to call ({period_label})</p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
                <tr>
                    <td align="center" style="padding-top:12px;">
                        <a href="{button_href}" style="display:inline-block;background:{button_gradient};color:#fff;font-size:13px;font-weight:600;text-decoration:none;padding:12px 28px;border-radius:10px;box-shadow:{button_shadow};">
                            {button_icon} {button_text}
                        </a>
                    </td>
                </tr>
            </table>
            '''
        else:
            return f'''
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:8px;">
                <tr>
                    <td align="center">
                        <table cellpadding="0" cellspacing="0" style="background-color:#2d2006;border-radius:8px;border:2px solid #f59e0b;">
                            <tr>
                                <td style="padding:10px 16px;">
                                    <p style="color:#fbbf24;margin:0 0 4px;font-weight:600;font-size:12px;">⚠️ It's {customer_time_str} for {first_name}</p>
                                    <p style="color:#fcd34d;margin:0;font-size:11px;">Prefers {period_label} ({self._format_time_range(window_start, window_end)})</p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
                <tr>
                    <td align="center" style="padding-top:12px;">
                        <a href="{button_href}" style="display:inline-block;background:{button_gradient};color:#fff;font-size:13px;font-weight:600;text-decoration:none;padding:12px 28px;border-radius:10px;box-shadow:{button_shadow};">
                            {button_icon} {button_text}
                        </a>
                    </td>
                </tr>
                <tr>
                    <td align="center" style="padding-top:6px;">
                        <p style="color:rgba(255,255,255,0.35);font-size:10px;margin:0;">
                            Tap to call anyway
                        </p>
                    </td>
                </tr>
            </table>
            '''

    def _format_time_range(self, start_hour, end_hour):
        """Format hour values to readable time range."""
        def format_hour(h):
            h = int(h) % 24
            if h == 0:
                return "12:00 AM"
            elif h < 12:
                return f"{h}:00 AM"
            elif h == 12:
                return "12:00 PM"
            else:
                return f"{h-12}:00 PM"

        return f"{format_hour(start_hour)} - {format_hour(end_hour)}"


# Singleton instance
email_service = EmailService()

