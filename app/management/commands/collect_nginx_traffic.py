import datetime
import subprocess
import re
from django.core.management.base import BaseCommand
from app.models import NginxDailyTraffic

LOG_FILE = "/var/log/nginx/access.log"

BOT_PATTERN = re.compile(
    r"(bot|crawl|spider|slurp|facebook|whatsapp|telegram|discord|preview|"
    r"curl|wget|python-requests|httpclient)",
    re.IGNORECASE
)

class Command(BaseCommand):
    help = "Collect daily nginx traffic (human vs bot)"

    def handle(self, *args, **kwargs):
        today = datetime.date.today()
        date_str = today.strftime("%d/%b/%Y")

        cmd = f"grep '{date_str}' {LOG_FILE}"
        lines = subprocess.getoutput(cmd).splitlines()

        human_ips = set()
        bot_ips = set()
        human_requests = 0
        bot_requests = 0

        for line in lines:
            ip = line.split()[0]

            if BOT_PATTERN.search(line):
                bot_requests += 1
                bot_ips.add(ip)
            else:
                human_requests += 1
                human_ips.add(ip)

        traffic = NginxDailyTraffic.objects(date=today).first()
        if not traffic:
            traffic = NginxDailyTraffic(date=today)

        traffic.total_requests = len(lines)
        traffic.human_requests = human_requests
        traffic.bot_requests = bot_requests
        traffic.human_unique_visitors = len(human_ips)
        traffic.bot_unique_visitors = len(bot_ips)

        traffic.save()

        self.stdout.write(
            f"{today} | "
            f"Human: {human_requests} ({len(human_ips)} uniques) | "
            f"Bot: {bot_requests} ({len(bot_ips)} uniques)"
        )

        self.check_spike(today, human_requests)

    def check_spike(self, today, today_requests):
        yesterday = today - datetime.timedelta(days=1)
        yesterday_data = NginxDailyTraffic.objects(date=yesterday).first()

        if not yesterday_data:
            return

        if today_requests > yesterday_data.human_requests * 2:
            self.send_alert(today_requests, yesterday_data.human_requests)

    def send_alert(self, today, yesterday):
        print(
            "🚨 TRAFFIC SPIKE ALERT 🚨\n"
            f"Yesterday: {yesterday}\n"
            f"Today: {today}"
        )
