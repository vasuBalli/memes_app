import datetime
import subprocess
import re
from django.core.management.base import BaseCommand
from app.models import NginxDailyTraffic

LOG_FILE = "/var/log/nginx/access.log"
DOMAIN = "memeverse.in"

BOT_PATTERN = re.compile(
    r"(bot|crawl|spider|slurp|facebook|whatsapp|telegram|discord|preview|"
    r"curl|wget|python-requests|httpclient)",
    re.IGNORECASE
)

class Command(BaseCommand):
    help = "Collect daily nginx traffic for memeverse domain only"

    def handle(self, *args, **kwargs):
        today = datetime.date.today()
        date_str = today.strftime("%d/%b/%Y")

        # get only today's logs
        cmd = f"grep '{date_str}' {LOG_FILE}"
        lines = subprocess.getoutput(cmd).splitlines()

        human_ips = set()
        bot_ips = set()
        human_requests = 0
        bot_requests = 0

        for line in lines:
            # ✅ DOMAIN FILTER (MOST IMPORTANT PART)
            if DOMAIN not in line:
                continue

            ip = line.split()[0]

            # 🤖 BOT CHECK
            if BOT_PATTERN.search(line):
                bot_requests += 1
                bot_ips.add(ip)
            else:
                human_requests += 1
                human_ips.add(ip)

        traffic = NginxDailyTraffic.objects(date=today).first()
        if not traffic:
            traffic = NginxDailyTraffic(date=today)

        traffic.total_requests = human_requests + bot_requests
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
