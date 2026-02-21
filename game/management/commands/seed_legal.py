"""Seed default Privacy Policy and Terms of Service content."""
from django.core.management.base import BaseCommand
from game.models import LegalDocument


PRIVACY_POLICY = """
<h1>Privacy Policy</h1>

<p><strong>Effective Date:</strong> February 2025</p>

<p>CashFlip ("we," "us," or "our") operates the CashFlip mobile gaming platform at <a href="https://cashflip.cash">cashflip.cash</a>. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our platform.</p>

<h2>1. Information We Collect</h2>

<h3>Personal Information</h3>
<ul>
<li><strong>Phone Number:</strong> Required for account creation and OTP verification. We use your phone number to send one-time verification codes via SMS or WhatsApp.</li>
<li><strong>Email Address:</strong> Optional, used for account recovery and communication if provided.</li>
<li><strong>Display Name:</strong> Optional, chosen by you for in-game identification.</li>
<li><strong>Mobile Money Account Details:</strong> Phone number linked to your mobile money account for deposits and withdrawals.</li>
</ul>

<h3>Automatically Collected Information</h3>
<ul>
<li><strong>Device Information:</strong> Device type, operating system, browser type, and unique device identifiers.</li>
<li><strong>Usage Data:</strong> Game session data, transaction history, login times, and interaction patterns.</li>
<li><strong>IP Address:</strong> Collected for security, fraud prevention, and rate limiting.</li>
<li><strong>Location Data:</strong> Country-level location derived from your IP address or phone number country code.</li>
</ul>

<h2>2. How We Use Your Information</h2>
<ul>
<li><strong>Account Management:</strong> To create, verify, and maintain your account.</li>
<li><strong>Game Services:</strong> To operate the CashFlip game, process stakes, calculate payouts, and manage your wallet balance.</li>
<li><strong>Transactions:</strong> To process deposits via mobile money and facilitate withdrawals to your mobile money account.</li>
<li><strong>Communication:</strong> To send verification codes, transaction confirmations, and important account notifications.</li>
<li><strong>Security:</strong> To detect and prevent fraud, abuse, and unauthorized access.</li>
<li><strong>Compliance:</strong> To comply with regulatory requirements under the Gaming Commission of Ghana and applicable laws.</li>
<li><strong>Improvement:</strong> To analyze usage patterns and improve our services.</li>
</ul>

<h2>3. SMS and Messaging</h2>
<p>By providing your phone number and opting into our text messaging program, you consent to receive one-time transactional security codes on your mobile device. Standard message and data rates may apply. For assistance, reply HELP to the number from which you received the message, or contact us at the support email listed below. To stop receiving messages, reply STOP at any time. Carriers are not liable for delayed or undelivered messages.</p>

<h2>4. Information Sharing</h2>
<p>We do not sell your personal information. We may share your information with:</p>
<ul>
<li><strong>Payment Processors:</strong> Mobile money providers (e.g., MTN MoMo, Vodafone Cash, AirtelTigo Money) to process deposits and withdrawals.</li>
<li><strong>Communication Providers:</strong> SMS and WhatsApp messaging services to deliver verification codes.</li>
<li><strong>Regulatory Authorities:</strong> The Gaming Commission of Ghana and other authorities as required by law.</li>
<li><strong>Service Providers:</strong> Cloud hosting, analytics, and security services that help us operate the platform.</li>
</ul>

<h2>5. Data Security</h2>
<p>We implement industry-standard security measures including:</p>
<ul>
<li>Encryption of data in transit (TLS/SSL) and at rest.</li>
<li>Secure authentication via one-time passwords (OTP).</li>
<li>Rate limiting and IP-based fraud detection.</li>
<li>Regular security audits and monitoring.</li>
</ul>

<h2>6. Data Retention</h2>
<p>We retain your personal information for as long as your account is active or as needed to provide services. Transaction records are retained as required by regulatory obligations. You may request account deletion by contacting our support team.</p>

<h2>7. Your Rights</h2>
<p>You have the right to:</p>
<ul>
<li>Access the personal information we hold about you.</li>
<li>Request correction of inaccurate information.</li>
<li>Request deletion of your account and associated data (subject to regulatory retention requirements).</li>
<li>Opt out of marketing communications.</li>
</ul>

<h2>8. Age Restriction</h2>
<p>CashFlip is intended for users aged 18 and above. We do not knowingly collect information from individuals under 18. If we become aware that we have collected information from a minor, we will take steps to delete it promptly.</p>

<h2>9. Changes to This Policy</h2>
<p>We may update this Privacy Policy from time to time. We will notify you of material changes by posting the updated policy on our platform. Your continued use of CashFlip after changes are posted constitutes acceptance of the revised policy.</p>

<h2>10. Contact Us</h2>
<p>If you have questions about this Privacy Policy or our data practices, contact us at:</p>
<ul>
<li><strong>Email:</strong> <a href="mailto:support@cashflip.cash">support@cashflip.cash</a></li>
<li><strong>Platform:</strong> <a href="https://cashflip.cash">cashflip.cash</a></li>
</ul>
""".strip()


TERMS_OF_SERVICE = """
<h1>Terms of Service</h1>

<p><strong>Effective Date:</strong> February 2025</p>

<p>Welcome to CashFlip. These Terms of Service ("Terms") govern your use of the CashFlip gaming platform operated at <a href="https://cashflip.cash">cashflip.cash</a>. By accessing or using CashFlip, you agree to be bound by these Terms.</p>

<h2>1. Eligibility</h2>
<ul>
<li>You must be at least <strong>18 years of age</strong> to use CashFlip.</li>
<li>You must be legally permitted to participate in online gaming in your jurisdiction.</li>
<li>You must provide accurate and truthful information during registration.</li>
<li>You are responsible for maintaining the security of your account credentials.</li>
</ul>

<h2>2. Account Registration</h2>
<p>To use CashFlip, you must create an account using a valid phone number. You agree to:</p>
<ul>
<li>Provide a valid phone number that belongs to you.</li>
<li>Verify your identity through one-time password (OTP) verification.</li>
<li>Not create multiple accounts or use another person's phone number.</li>
<li>Keep your account information up to date.</li>
</ul>

<h2>3. Text Messaging Terms</h2>
<p>By providing your phone number and opting into our text messaging program, you consent to receive a one-time transactional security code on your mobile device. Standard message and data rates may apply. For assistance, reply HELP to the number from which you received the message, or contact us at <a href="mailto:support@cashflip.cash">support@cashflip.cash</a>. To stop receiving messages, reply STOP at any time. Carriers are not liable for delayed or undelivered messages.</p>

<h2>4. Game Rules</h2>
<ul>
<li><strong>Stake:</strong> You select a stake amount from your wallet balance to begin a game session.</li>
<li><strong>Gameplay:</strong> Each flip reveals a currency denomination. The denomination value shown is your payout for that flip.</li>
<li><strong>Cashout:</strong> You may cash out your accumulated winnings at any time during a session (subject to minimum flip requirements).</li>
<li><strong>Game Over:</strong> A zero denomination ends the session. Any uncashed balance from the current session is forfeited.</li>
<li><strong>Fairness:</strong> Game outcomes are determined by our server-side engine. Results are final and non-reversible.</li>
</ul>

<h2>5. Deposits and Withdrawals</h2>
<ul>
<li><strong>Deposits:</strong> You may fund your wallet via supported mobile money providers. Minimum deposit amounts apply.</li>
<li><strong>Withdrawals:</strong> You may withdraw your wallet balance to your registered mobile money account. Processing times may vary.</li>
<li><strong>Fees:</strong> CashFlip does not charge deposit or withdrawal fees. Your mobile money provider may charge standard transaction fees.</li>
<li><strong>Limits:</strong> Maximum cashout limits per session and per transaction apply as configured by the platform.</li>
</ul>

<h2>6. Responsible Gaming</h2>
<p>CashFlip is committed to responsible gaming. We encourage you to:</p>
<ul>
<li>Set personal limits on your gaming activity and spending.</li>
<li>Take regular breaks during gaming sessions.</li>
<li>Not use gaming as a source of income.</li>
<li>Seek help if you believe you have a gambling problem.</li>
</ul>
<p>If you need assistance, please contact the <strong>Gaming Commission of Ghana</strong> or a local responsible gambling helpline.</p>

<h2>7. Prohibited Activities</h2>
<p>You agree not to:</p>
<ul>
<li>Use bots, scripts, or automated tools to interact with the platform.</li>
<li>Attempt to exploit bugs, glitches, or vulnerabilities in the game.</li>
<li>Engage in money laundering, fraud, or any illegal activity.</li>
<li>Create multiple accounts or use false identities.</li>
<li>Interfere with or disrupt the platform's operation.</li>
<li>Share your account with third parties.</li>
</ul>

<h2>8. Account Suspension and Termination</h2>
<p>We reserve the right to suspend or terminate your account if:</p>
<ul>
<li>You violate these Terms.</li>
<li>We detect fraudulent or suspicious activity.</li>
<li>Required by law or regulatory authorities.</li>
<li>You request account closure.</li>
</ul>
<p>Upon termination, any remaining wallet balance (excluding bonuses) will be made available for withdrawal, subject to verification.</p>

<h2>9. Intellectual Property</h2>
<p>All content, graphics, logos, animations, sounds, and software on CashFlip are owned by or licensed to us and are protected by intellectual property laws. You may not copy, distribute, or modify any part of our platform without written permission.</p>

<h2>10. Limitation of Liability</h2>
<ul>
<li>CashFlip is provided "as is" without warranties of any kind.</li>
<li>We are not liable for losses arising from technical issues, network outages, or service interruptions.</li>
<li>Our total liability is limited to the balance in your wallet at the time of any claim.</li>
<li>We are not responsible for any losses from your gaming activities.</li>
</ul>

<h2>11. Regulatory Compliance</h2>
<p>CashFlip is licensed and regulated by the <strong>Gaming Commission of Ghana</strong>. We comply with all applicable gaming laws and regulations. We reserve the right to verify your identity and report suspicious activities as required by law.</p>

<h2>12. Dispute Resolution</h2>
<p>Any disputes arising from the use of CashFlip shall be resolved through:</p>
<ul>
<li>First, contacting our support team at <a href="mailto:support@cashflip.cash">support@cashflip.cash</a>.</li>
<li>If unresolved, filing a complaint with the Gaming Commission of Ghana.</li>
<li>As a last resort, through the courts of Ghana.</li>
</ul>

<h2>13. Changes to These Terms</h2>
<p>We may modify these Terms at any time. Continued use of CashFlip after changes are posted constitutes acceptance of the revised Terms. Material changes will be communicated via the platform.</p>

<h2>14. Governing Law</h2>
<p>These Terms are governed by and construed in accordance with the laws of the Republic of Ghana.</p>

<h2>15. Contact Us</h2>
<p>For questions or concerns about these Terms, contact us at:</p>
<ul>
<li><strong>Email:</strong> <a href="mailto:support@cashflip.cash">support@cashflip.cash</a></li>
<li><strong>Platform:</strong> <a href="https://cashflip.cash">cashflip.cash</a></li>
</ul>
""".strip()


SMS_DISCLOSURE = (
    "By providing your phone number, you consent to receive a one-time "
    "verification code via SMS or WhatsApp. Standard message and data rates "
    "may apply. For assistance, reply HELP or contact support@cashflip.cash. "
    "To stop receiving messages, reply STOP. Carriers are not liable for "
    "delayed or undelivered messages."
)


class Command(BaseCommand):
    help = 'Seed default Privacy Policy and Terms of Service content'

    def handle(self, *args, **options):
        legal = LegalDocument.get_legal()
        updated = []

        if not legal.privacy_policy:
            legal.privacy_policy = PRIVACY_POLICY
            updated.append('privacy_policy')
            self.stdout.write('  Privacy Policy seeded')

        if not legal.terms_of_service:
            legal.terms_of_service = TERMS_OF_SERVICE
            updated.append('terms_of_service')
            self.stdout.write('  Terms of Service seeded')

        if legal.sms_disclosure == LegalDocument._meta.get_field('sms_disclosure').default:
            legal.sms_disclosure = SMS_DISCLOSURE
            updated.append('sms_disclosure')
            self.stdout.write('  SMS Disclosure updated')

        if updated:
            legal.save(update_fields=updated + ['updated_at'])
            self.stdout.write(self.style.SUCCESS(f'Legal documents seeded ({", ".join(updated)})'))
        else:
            self.stdout.write('Legal documents already have content — skipping')
