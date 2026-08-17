#!/usr/bin/env python3
"""Run the separate JobRadar LiveKit Agents worker from the backend directory."""
from app.services.interview.voice.livekit_agent import main


if __name__ == "__main__":
    main()
