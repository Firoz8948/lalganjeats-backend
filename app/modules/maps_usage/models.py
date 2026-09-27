# backend/app/modules/maps_usage/models.py
"""
Cost-monitoring tables for paid Google Maps Platform calls.

- maps_api_usage_logs: one row per outbound Google API request (what, why,
  status, estimated ₹). Nothing is logged for cache hits or haversine
  fallbacks because those cost nothing.
- road_distance_cache: memoised Distance Matrix results keyed on
  coordinates rounded to 4 dp (~11 m). Roads do not move, so a hit is
  reused for weeks instead of paying Google again.
"""
from sqlalchemy import Column, DateTime, Float, Integer, Numeric, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class MapsApiUsageLog(Base):
    __tablename__ = "maps_api_usage_logs"

    id = Column(Integer, primary_key=True)
    api_name = Column(String(40), nullable=False, index=True)   # distance_matrix
    purpose = Column(String(60), nullable=False, index=True)    # listing_zone_check | menu_delivery_quote | order_placement | ...
    origin_lat = Column(Float, nullable=True)
    origin_lng = Column(Float, nullable=True)
    dest_lat = Column(Float, nullable=True)
    dest_lng = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default="ok")   # ok | zero_results | error
    error = Column(Text, nullable=True)
    elements = Column(Integer, nullable=False, default=1)
    estimated_cost_inr = Column(Numeric(10, 4), nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class RoadDistanceCache(Base):
    __tablename__ = "road_distance_cache"

    id = Column(Integer, primary_key=True)
    # "o_lat,o_lng|d_lat,d_lng" with 4-decimal rounding
    cache_key = Column(String(64), nullable=False, unique=True, index=True)
    origin_lat = Column(Float, nullable=False)
    origin_lng = Column(Float, nullable=False)
    dest_lat = Column(Float, nullable=False)
    dest_lng = Column(Float, nullable=False)
    distance_km = Column(Float, nullable=False)
    duration_min = Column(Integer, nullable=False)
    source = Column(String(20), nullable=False, default="google")
    hits = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
