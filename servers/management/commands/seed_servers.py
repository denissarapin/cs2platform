from django.core.management.base import BaseCommand
from servers.models import Server

class Command(BaseCommand):
    help = "Создаёт примерные записи серверов"

    def handle(self, *args, **options):
        samples = [
            dict(name='Warsaw #1', ip='127.0.0.1', game_port=27015, query_port=27015, location='Warsaw', is_allocated=False),
            dict(name='Gdansk #2', ip='127.0.0.1', game_port=27016, query_port=27016, location='Gdansk', is_allocated=True),
        ]
        for s in samples:
            obj, created = Server.objects.get_or_create(ip=s['ip'], game_port=s['game_port'], defaults=s)
            self.stdout.write(self.style.SUCCESS(f'{"CREATED" if created else "EXISTS"}: {obj}'))
