from rest_framework import generics, status, permissions
from .models import Tournament, Match
from .serializers import TournamentSerializer, ReportMatchSerializer
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response

class TournamentListAPIView(generics.ListAPIView):
    queryset = Tournament.objects.all()
    serializer_class = TournamentSerializer

class TournamentDetailAPIView(generics.RetrieveAPIView):
    queryset = Tournament.objects.all()
    serializer_class = TournamentSerializer

class ReportMatchAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        tournament = get_object_or_404(Tournament, pk=pk)
        serializer = ReportMatchSerializer(data=request.data)
        if serializer.is_valid():
            match_id = serializer.validated_data['match_id']
            score_a = serializer.validated_data['score_a']
            score_b = serializer.validated_data['score_b']

            match = get_object_or_404(Match, pk=match_id, tournament=tournament)
            match.set_result(score_a, score_b)

            return Response({"message": "Score updated"})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)