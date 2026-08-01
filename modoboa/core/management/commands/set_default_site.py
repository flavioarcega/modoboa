"""
A simple managemenent command to update the default site.

See `https://docs.djangoproject.com/en/dev/ref/contrib/sites/`_.
"""

import os
import uuid
import shutil

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from oauth2_provider.models import get_application_model


class Command(BaseCommand):
    """Management command to set the default site."""

    help = "Set default site (see django.contrib.sites)"  # NOQA:A003

    def add_arguments(self, parser):
        """Define command arguments."""
        parser.add_argument("hostname", type=str)
        parser.add_argument(
            "--frontend",
            action="store_true",
            default=False,
            help="Execute frontend initialisation",
        )
        parser.add_argument(
            "--relative-urls-in-config",
            action="store_true",
            default=False,
            help="Use relative urls in generated config.json file",
        )
        parser.add_argument(
            "--dev",
            action="store_true",
            default=False,
            help="Setup dev environment. DO NOT USE IN PRODUCTION",
        )

    def handle(self, *args, **options):
        """Command entry point."""
        if "hostname" not in options:
            raise CommandError("You must provide a hostname")
        site = Site.objects.get(pk=1)
        site.domain = options["hostname"]
        site.name = options["hostname"]
        site.save()

        if not options["frontend"]:
            return

        call_command("collectstatic", "--noinput")

        app_model = get_application_model()
        frontend_application = app_model.objects.filter(name="modoboa_frontend")

        redirect_uri = f"https://{site.domain}/login/logged"

        client_id = ""
        if options["dev"]:
            redirect_uri = "https://localhost:3000/login/logged"
            client_id = "LVQbfIIX3khWR3nDvix1u9yEGHZUxcx53bhJ7FlD"

        if not frontend_application.exists():
            if not options["dev"]:
                client_id = str(uuid.uuid4())
            call_command(
                "createapplication",
                "--algorithm=RS256",
                f"--redirect-uris={redirect_uri}",
                "--name=modoboa_frontend",
                f"--client-id={client_id}",
                f"--post-logout-redirect-uris=https://localhost:3000/",
                "--skip-authorization",
                "public",
                "authorization-code",
            )
        else:
            app = frontend_application.first()
            app.redirect_uris = redirect_uri
            app.post_logout_redirect_uris = site.domain
            app.save()
            client_id = app.client_id

        frontend_source_dir = os.path.join(
            os.path.dirname(__file__), "../../../frontend_dist/"
        )
        frontend_target_dir = f"{settings.BASE_DIR}/www"
        shutil.copytree(frontend_source_dir, frontend_target_dir, dirs_exist_ok=True)

        api_base_url = "/api/v2"
        api_doc_url = "/api/schema-v2/swagger/"
        oauth_authority_url = "/api/o"
        if not options["relative_urls_in_config"]:
            api_base_url = f"https://{site.domain}{api_base_url}"
            api_doc_url = f"https://{site.domain}{api_doc_url}"
            oauth_authority_url = f"https://{site.domain}{oauth_authority_url}"
            oauth_post_logout_redirect_uri = f"http://{site.domain}/"
        else:
            oauth_post_logout_redirect_uri = ""

        with open(f"{frontend_target_dir}/config.json", "w") as fp:
            fp.write(f"""\
{{
    "API_BASE_URL": "{api_base_url}",
    "API_DOC_URL": "{api_doc_url}",
    "OAUTH_AUTHORITY_URL": "{oauth_authority_url}",
    "OAUTH_CLIENT_ID": "{client_id}",
    "OAUTH_REDIRECT_URI": "{redirect_uri}",
    "OAUTH_POST_REDIRECT_URI": "{oauth_post_logout_redirect_uri}"
}}""")
