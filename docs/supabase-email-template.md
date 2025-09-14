# Supabase Email Template Configuration

## Configure OTP Email Template

To send OTP codes instead of magic links, update the Supabase email template:

### Steps:
1. Go to Supabase Dashboard → Authentication → Email Templates
2. Edit the "Magic Link" template
3. Replace the template content with the following:

```html
<h2>Your Verification Code</h2>

<p>Hello,</p>

<p>You requested to sign in to your account. Please use the verification code below:</p>

<div style="background-color: #f4f4f4; padding: 20px; text-align: center; font-size: 24px; font-weight: bold; letter-spacing: 3px; margin: 20px 0; border-radius: 8px;">
  {{ .Token }}
</div>

<p><strong>This code will expire in 60 minutes.</strong></p>

<p>If you didn't request this code, you can safely ignore this email.</p>

<p>Thanks,<br>Your BlueBubbles Integration Team</p>
```

### Key Template Variables:
- `{{ .Token }}` - The 6-digit OTP code
- `{{ .ConfirmationURL }}` - Magic link (remove this)

### Template Features:
- Clear, prominent OTP display
- Professional styling
- Expiration notice
- Security disclaimer

After saving this template, Supabase will send OTP codes instead of magic links when using `sign_in_with_otp()`.
