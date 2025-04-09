import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import pandas as pd
from io import BytesIO

class EmailSender:
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.from_email = self.smtp_username

    def create_excel_attachment(self, data):
        """Convert query results to Excel file"""
        try:
            # Convert data to DataFrame
            df = pd.DataFrame(data)
            
            # Create Excel file in memory
            excel_buffer = BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)
            
            return excel_buffer.getvalue()
        except Exception as e:
            print(f"Error creating Excel attachment: {str(e)}")
            return None

    def send_report(self, to_email, results):
        """Send query results as Excel attachment"""
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = 'Your Requested Report'

            body = """
                <html>
                <head>
                <style>
                    body {
                    font-family: Arial, sans-serif;
                    font-size: 14px;
                    color: #333333;
                    }
                    .container {
                    padding: 20px;
                    }
                    .footer {
                    margin-top: 30px;
                    font-size: 12px;
                    color: #888888;
                    }
                </style>
                </head>
                <body>
                <div class="container">
                    <p>Hello,</p>

                    <p>Please find the attached Excel report you requested.</p>

                    <p>Best regards,<br>
                    <strong>AI Report Assistant</strong></p>

                    <div class="footer">
                    This is an automated email — please do not reply directly.
                    </div>
                </div>
                </body>
                </html>
                """
            msg.attach(MIMEText(body, 'html'))

            # Create Excel attachment
            excel_data = self.create_excel_attachment(results)
            if excel_data:
                attachment = MIMEApplication(excel_data, _subtype='xlsx')
                attachment.add_header('Content-Disposition', 'attachment', filename='report.xlsx')
                msg.attach(attachment)

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            print(f"Report sent successfully to {to_email}")
            return True

        except Exception as e:
            print(f"Error sending report: {str(e)}")
            return False

    def send_error_notification(self, to_email, error_message):
        """Send error notification to user"""
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = 'Error Generating Your Report'

            # Add body
            body = f"""
            Hello,

            We encountered an error while generating your report:
            {error_message}

            Please try again or contact support if the issue persists.

            Best regards,
            AI Report Assistant
            """
            msg.attach(MIMEText(body, 'plain'))

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            print(f"Error notification sent to {to_email}")
            return True

        except Exception as e:
            print(f"Error sending notification: {str(e)}")
            return False
