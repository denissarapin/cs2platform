from rest_framework import serializers
from .models import Tournament, Match
from teams.models import Team

class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ['id', 'name', 'tag']

class MatchSerializer(serializers.ModelSerializer):
    team_a = TeamSerializer()
    team_b = TeamSerializer()

    class Meta:
        model = Match
        fields = ['id', 'round', 'team_a', 'team_b', 'score_a', 'score_b', 'status']

class TournamentSerializer(serializers.ModelSerializer):
    matches = MatchSerializer(many=True, read_only=True)

    class Meta:
        model = Tournament
        fields = ['id', 'name', 'description', 'status', 'start_date', 'end_date', 'matches']

class ReportMatchSerializer(serializers.Serializer):
    match_id = serializers.IntegerField()
    score_a = serializers.IntegerField()
    score_b = serializers.IntegerField()

