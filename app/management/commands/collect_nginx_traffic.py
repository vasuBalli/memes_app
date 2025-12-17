import datetime
import subprocess
from django.core.management.base import BaseCommand
from app.models import NginxDailyTraffic

LOG_FILE = "/var/log/nginx/access.log"

class Command(BaseCommand):
    help = "Collect daily traffic from Nginx access logs"

    def handle(self, *args, **kwargs):
        today = datetime.date.today()
        date_str = today.strftime("%d/%b/%Y")

        total_cmd = f"grep '{date_str}' {LOG_FILE} | wc -l"
        unique_cmd = f"grep '{date_str}' {LOG_FILE} | awk '{{print $1}}' | sort | uniq | wc -l"

        try:
            total_requests = int(subprocess.getoutput(total_cmd))
            unique_visitors = int(subprocess.getoutput(unique_cmd))
        except Exception as e:
            self.stderr.write(str(e))
            return

        traffic = NginxDailyTraffic.objects(date=today).first()
        if not traffic:
            traffic = NginxDailyTraffic(date=today)

        traffic.total_requests = total_requests
        traffic.unique_visitors = unique_visitors
        traffic.save()

        self.stdout.write(
            f"Saved traffic for {today}: "
            f"{total_requests} requests, {unique_visitors} visitors"
        )
