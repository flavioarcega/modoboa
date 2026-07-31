"""
A simple managemenent command to update the default site.

See `https://docs.djangoproject.com/en/dev/ref/contrib/sites/`_.
"""

import os
import sys
import uuid
import shutil
import subprocess

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

    def _exec_django_command(self, name, cwd, *args):
        """Run a django command for the freshly created project

        :param name: the command name
        :param cwd: the directory where the command must be executed
        """
        cmd = [sys.executable, "manage.py", name]
        cmd.extend(args)
        if not self._verbose:
            p = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd
            )
            output = p.communicate()
        else:
            p = subprocess.Popen(cmd, cwd=cwd)
            p.wait()
            output = None
        if p.returncode:
            if output:
                print(
                    "\n".join([line.decode() for line in output if line is not None]),
                    file=sys.stderr,
                )
            print(f"{cmd} failed, check your configuration", file=sys.stderr)

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

        self._exec_django_command("collectstatic", "--noinput")

        os.mkdir("/www/media")

        app_model = get_application_model()
        frontend_application = app_model.objects.filter(name="modoboa_frontend")

        # TODO : improve support for multiple allowed_host for frontend
        base_uris_list = [f"https://{host}" for host in site.domain]
        base_uris = " ".join(base_uris_list)
        base_uri = base_uris_list[0]

        redirect_uris = " ".join([f"{uri}/login/logged" for uri in base_uris_list])
        if not options["relative_urls_in_config"]:
            redirect_uri = redirect_uris.split(" ")[0]
        else:
            redirect_uri = "/login/logged"

        client_id = ""
        if options["dev"]:
            base_uri = "https://localhost:3000/"
            base_uris = base_uri
            redirect_uri = "https://localhost:3000/login/logged"
            redirect_uris = redirect_uri
            client_id = "LVQbfIIX3khWR3nDvix1u9yEGHZUxcx53bhJ7FlD"
        if not frontend_application.exists():
            if not options["dev"]:
                client_id = str(uuid.uuid4())
            call_command(
                "createapplication",
                "--algorithm=RS256",
                f"--redirect-uris={redirect_uris}",
                "--name=modoboa_frontend",
                f"--client-id={client_id}",
                f"--post-logout-redirect-uris={base_uris}",
                "--skip-authorization",
                "public",
                "authorization-code",
            )
        else:
            app = frontend_application.first()
            app.redirect_uris = redirect_uris
            app.post_logout_redirect_uris = base_uris
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
            api_base_url = f"{base_uri}{api_base_url}"
            api_doc_url = f"{base_uri}{api_doc_url}"
            oauth_authority_url = f"{base_uri}{oauth_authority_url}"
            oauth_post_logout_redirect_uri = base_uri
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
