"""
Guest Persona definitions for the Ancillary Revenue Engine.

Each persona maps to a set of AncillaryContext guest-profile fields that
override the hotel-wide defaults.  The persona is supplied as a query
parameter; the service blends it with real hotel data to build context.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.schemas.ancillaries import GuestPersona


@dataclass(frozen=True)
class PersonaProfile:
    """Guest-context overrides applied when a persona is selected."""

    estimated_eligible_guests: int
    avg_stay_length: float
    vehicle_flag: bool = False
    ev_vehicle_flag: bool = False
    pet_flag: bool = False


# Map persona → profile defaults
# "estimated_eligible_guests" is a fraction of hotel rooms; the service will
# scale this relative to the actual hotel size when building context.
PERSONAS: dict[GuestPersona, PersonaProfile] = {
    GuestPersona.hotel_wide: PersonaProfile(
        estimated_eligible_guests=100,
        avg_stay_length=1.8,
        vehicle_flag=True,
    ),
    GuestPersona.business_traveler: PersonaProfile(
        estimated_eligible_guests=40,
        avg_stay_length=1.5,
        vehicle_flag=True,
    ),
    GuestPersona.conference_attendee: PersonaProfile(
        estimated_eligible_guests=60,
        avg_stay_length=2.5,
        vehicle_flag=True,
    ),
    GuestPersona.leisure_couple: PersonaProfile(
        estimated_eligible_guests=30,
        avg_stay_length=2.2,
        vehicle_flag=True,
    ),
    GuestPersona.family: PersonaProfile(
        estimated_eligible_guests=25,
        avg_stay_length=3.0,
        vehicle_flag=True,
    ),
    GuestPersona.resort_guest: PersonaProfile(
        estimated_eligible_guests=50,
        avg_stay_length=3.5,
        vehicle_flag=False,
    ),
    GuestPersona.ev_traveler: PersonaProfile(
        estimated_eligible_guests=10,
        avg_stay_length=1.8,
        vehicle_flag=True,
        ev_vehicle_flag=True,
    ),
    GuestPersona.pet_traveler: PersonaProfile(
        estimated_eligible_guests=8,
        avg_stay_length=2.0,
        vehicle_flag=True,
        pet_flag=True,
    ),
}
