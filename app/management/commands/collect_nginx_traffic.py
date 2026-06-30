from django.core.management.base import BaseCommand
from app.models import Memes
import cloudinary
import cloudinary.api


class Command(BaseCommand):

    def import_resources(self, resource_type):
        next_cursor = None
        created = 0

        while True:

            response = cloudinary.api.resources(
                type="upload",
                resource_type=resource_type,
                prefix="instagram_memes/",
                max_results=500,
                next_cursor=next_cursor
            )

            resources = response.get("resources", [])

            print(
                f"{resource_type}: Found {len(resources)} resources"
            )

            for resource in resources:

                secure_url = resource["secure_url"]

                if Memes.objects.filter(file=secure_url).exists():
                    continue

                public_id = resource["public_id"]

                thumbnail = None

                if resource_type == "video":
                    thumbnail = (
                        f"https://res.cloudinary.com/"
                        f"{cloudinary.config().cloud_name}/video/upload/"
                        f"so_0/{public_id}.jpg"
                    )

                Memes.objects.create(
                    title=public_id.split("/")[-1],
                    file=secure_url,
                    thumbnail=thumbnail,
                    type=resource_type,
                    language="english",
                    tags=[],
                    user_name="Memeverse"
                )

                created += 1

            next_cursor = response.get("next_cursor")

            if not next_cursor:
                break

        return created

    def handle(self, *args, **kwargs):

        total = 0

        total += self.import_resources("image")
        total += self.import_resources("video")

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {total} files"
            )
        )