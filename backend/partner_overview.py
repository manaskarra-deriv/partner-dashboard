"""
Partner Overview Tab Backend APIs

This module contains all the backend APIs for the Partner Overview tab:
- Partner overview statistics
- Global tier progression
- Country breakdown for tier progression
- Partner tier movement details
"""

from flask import request, jsonify
import logging
import traceback
import json
import pandas as pd
from datetime import datetime
import numpy as np
from collections import OrderedDict
from db_integration import db
from utils import TIER_MOVEMENT_SCORES, get_tier_movement_score, validate_partner_data

logger = logging.getLogger(__name__)

def register_partner_overview_routes(app, get_partner_data):
    """Register all Partner Overview tab routes"""

    @app.route('/api/partner-overview', methods=['GET'])
    def get_partner_overview():
        """Get partner overview statistics"""
        try:
            partner_data = get_partner_data()
            if partner_data is None:
                return jsonify({'error': 'No data available'}), 400

            # Get unique partners data (one record per partner) - use latest values to match list endpoint
            unique_partners = partner_data.groupby('partner_id').agg({
                'country': 'last',
                'partner_tier': 'last',
                'total_earnings': 'sum',
                'active_clients': 'last',
                'new_active_clients': 'sum',
                'total_deposits': 'sum',
                'is_app_dev': 'last'
            }).reset_index()

            # UPDATED: Separate active and inactive partners
            active_partners = unique_partners[unique_partners['partner_tier'] != 'Inactive']
            inactive_partners = unique_partners[unique_partners['partner_tier'] == 'Inactive']

            # Calculate top countries based on ACTIVE partners only (exclude Inactive from country counts)
            top_countries_series = active_partners['country'].value_counts().head(5)
            top_countries_dict = {}
            for country, count in top_countries_series.items():
                top_countries_dict[country] = int(count)

            # Calculate tier distribution including Inactive tier for visibility
            tier_counts = unique_partners['partner_tier'].value_counts()
            tier_order = ['Platinum', 'Gold', 'Silver', 'Bronze', 'Inactive']
            tier_distribution_dict = {}
            for tier in tier_order:
                if tier in tier_counts:
                    tier_distribution_dict[tier] = int(tier_counts[tier])

            # Calculate metrics using ACTIVE partners only (exclude Inactive from totals)
            total_revenue = float(active_partners['total_earnings'].sum())
            total_deposits = float(active_partners['total_deposits'].sum())
            latest_active_clients = int(active_partners['active_clients'].sum())
            total_new_clients = int(active_partners['new_active_clients'].sum())
            api_developers = int(active_partners['is_app_dev'].sum())
            avg_earnings_per_partner = total_revenue / len(active_partners) if len(active_partners) > 0 else 0

            # Calculate overview metrics - using OrderedDict to preserve order
            # UPDATED: Show active partners count, excluding Inactive partners
            overview = OrderedDict([
                ('active_partners', len(active_partners)),  # Active partners only (excluding Inactive)
                ('total_partners', len(unique_partners)),   # Keep total for reference (including Inactive)
                ('total_revenue', total_revenue),           # From active partners only
                ('total_deposits', total_deposits),         # From active partners only
                ('total_active_clients', int(latest_active_clients)),
                ('total_new_clients', total_new_clients),
                ('avg_earnings_per_partner', float(avg_earnings_per_partner)),  # Based on active partners
                ('top_countries', top_countries_dict),      # Active partners only
                ('tier_distribution', tier_distribution_dict),  # Include Inactive for visibility
                ('api_developers', api_developers)
            ])

            return jsonify(overview)

        except Exception as e:
            logger.error(f"Error getting partner overview: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/partner-tier-progression', methods=['GET'])
    def get_partner_tier_progression():
        """
        Get partner tier progression data with movement tracking.
        Supports filtering by country and tier transitions.
        """
        try:
            partner_data = get_partner_data()
            if partner_data is None:
                return jsonify({'error': 'No data available'}), 400

            country = request.args.get('country')
            from_tier = request.args.get('from_tier')
            to_tier = request.args.get('to_tier')
            is_global: bool = request.args.get('is_global', 'false').lower() == 'true'

            # Handle URL encoding where + should become spaces
            if country:
                country = country.replace('+', ' ')

            # For global requests, don't filter by country
            if not is_global and not country:
                return jsonify({'error': 'Either country parameter or is_global=true is required'}), 400

            # Filter data by country or use all data for global
            if is_global:
                filtered_data = partner_data.copy()
            else:
                # Filter CSV data by country
                filtered_data = partner_data[partner_data['country'] == country].copy()

            if filtered_data.empty:
                return jsonify({
                    'success': True,
                    'data': {
                        'monthly_progression': [],
                        'summary': {'total_positive_score': 0, 'total_negative_score': 0, 'weighted_net_movement': 0, 'total_months': 0, 'avg_monthly_net_movement': 0}
                    },
                    'country': country
                })

            # Use shared tier movement scores
            tier_movement_scores = TIER_MOVEMENT_SCORES

            # Sort data by partner and month to track progression
            filtered_data = filtered_data.sort_values(['partner_id', 'month'])

            # Track monthly progression
            monthly_progression = {}

            # Group by partner to track their tier changes over time
            for partner_id, partner_data_group in filtered_data.groupby('partner_id'):
                partner_months = partner_data_group.sort_values('month')

                # Track tier changes month over month
                for i in range(1, len(partner_months)):
                    current_month = partner_months.iloc[i]
                    previous_month = partner_months.iloc[i-1]

                    current_tier = current_month['partner_tier']
                    previous_tier = previous_month['partner_tier']
                    month_str = current_month['month'].strftime('%b %Y')

                    # Apply tier filters if specified
                    tier_filter_match = True
                    if from_tier and from_tier != 'All Tiers' and previous_tier != from_tier:
                        tier_filter_match = False
                    if to_tier and to_tier != 'All Tiers' and current_tier != to_tier:
                        tier_filter_match = False

                    if not tier_filter_match:
                        continue

                    # Calculate tier movement score using specific transition values
                    movement_key = (previous_tier, current_tier)
                    movement_score = tier_movement_scores.get(movement_key, 0)

                    # Initialize month data if not exists
                    if month_str not in monthly_progression:
                        monthly_progression[month_str] = {
                            'positive_movements': 0,
                            'negative_movements': 0,
                            'positive_score': 0,
                            'negative_score': 0,
                            'total_partners_with_movement': 0,
                            'partner_movements': [],
                            # Add country breakdown tracking for global requests
                            'country_breakdowns': {
                                'positive': {},  # {country: {score: X, movement_count: Y}}
                                'negative': {}   # {country: {score: X, movement_count: Y}}
                            } if is_global else None
                        }

                    # Track individual partner movements for detailed analysis
                    if movement_score != 0:
                        monthly_progression[month_str]['total_partners_with_movement'] += 1
                        monthly_progression[month_str]['partner_movements'].append({
                            'partner_id': partner_id,
                            'from_tier': previous_tier,
                            'to_tier': current_tier,
                            'movement_score': movement_score
                        })

                        if movement_score > 0:
                            monthly_progression[month_str]['positive_movements'] += 1
                            monthly_progression[month_str]['positive_score'] += movement_score

                            # Track country breakdown for positive movements (global only)
                            if is_global and monthly_progression[month_str]['country_breakdowns']:
                                country = current_month['country']
                                if pd.notna(country):
                                    if country not in monthly_progression[month_str]['country_breakdowns']['positive']:
                                        monthly_progression[month_str]['country_breakdowns']['positive'][country] = {
                                            'score': 0, 'movement_count': 0
                                        }
                                    monthly_progression[month_str]['country_breakdowns']['positive'][country]['score'] += movement_score
                                    monthly_progression[month_str]['country_breakdowns']['positive'][country]['movement_count'] += 1
                        else:
                            monthly_progression[month_str]['negative_movements'] += 1
                            monthly_progression[month_str]['negative_score'] += movement_score

                            # Track country breakdown for negative movements (global only)
                            if is_global and monthly_progression[month_str]['country_breakdowns']:
                                country = current_month['country']
                                if pd.notna(country):
                                    if country not in monthly_progression[month_str]['country_breakdowns']['negative']:
                                        monthly_progression[month_str]['country_breakdowns']['negative'][country] = {
                                            'score': 0, 'movement_count': 0
                                        }
                                    monthly_progression[month_str]['country_breakdowns']['negative'][country]['score'] += movement_score
                                    monthly_progression[month_str]['country_breakdowns']['negative'][country]['movement_count'] += 1

            # Calculate weighted net movement for each month
            formatted_monthly_data = []
            total_positive_score = 0
            total_negative_score = 0

            # Sort months chronologically (latest first to match other endpoints)
            sorted_months = sorted(monthly_progression.keys(),
                                  key=lambda x: pd.to_datetime(x, format='%b %Y'),
                                  reverse=True)

            for month_str in sorted_months:
                month_data = monthly_progression[month_str]
                weighted_net_movement = month_data['positive_score'] + month_data['negative_score']

                # Remove detailed partner movements from the response (too much data)
                # But add tier transition summaries for client-side filtering
                tier_transitions = {}
                if is_global:
                    for movement in month_data['partner_movements']:
                        transition_key = f"{movement['from_tier']} -> {movement['to_tier']}"
                        if transition_key not in tier_transitions:
                            tier_transitions[transition_key] = {
                                'count': 0,
                                'total_score': 0,
                                'from_tier': movement['from_tier'],
                                'to_tier': movement['to_tier']
                            }
                        tier_transitions[transition_key]['count'] += 1
                        tier_transitions[transition_key]['total_score'] += movement['movement_score']

                monthly_summary = {
                    'month': month_str,
                    'positive_movements': month_data['positive_movements'],
                    'negative_movements': month_data['negative_movements'],
                    'positive_score': month_data['positive_score'],
                    'negative_score': month_data['negative_score'],
                    'weighted_net_movement': weighted_net_movement,
                    'total_partners_with_movement': month_data['total_partners_with_movement'],
                    # Add tier transitions for client-side filtering
                    'tier_transitions': tier_transitions if is_global else None
                }

                # Add pre-calculated country breakdowns for global requests
                if is_global and month_data['country_breakdowns']:
                    # Calculate true net movement for each country (positive + negative scores)
                    true_country_net = {}

                    # Sum positive movement scores per country
                    for country, data in month_data['country_breakdowns']['positive'].items():
                        if country not in true_country_net:
                            true_country_net[country] = {'positive_score': 0, 'negative_score': 0, 'positive_count': 0, 'negative_count': 0}
                        true_country_net[country]['positive_score'] = data['score']
                        true_country_net[country]['positive_count'] = data['movement_count']

                    # Sum negative movement scores per country
                    for country, data in month_data['country_breakdowns']['negative'].items():
                        if country not in true_country_net:
                            true_country_net[country] = {'positive_score': 0, 'negative_score': 0, 'positive_count': 0, 'negative_count': 0}
                        true_country_net[country]['negative_score'] = data['score']
                        true_country_net[country]['negative_count'] = data['movement_count']

                    # Sort positive countries by score (highest first)
                    positive_countries = []
                    for country, data in month_data['country_breakdowns']['positive'].items():
                        true_net = true_country_net[country]['positive_score'] + true_country_net[country]['negative_score']
                        total_movements = true_country_net[country]['positive_count'] + true_country_net[country]['negative_count']
                        positive_countries.append({
                            'rank': 0,  # Will be set below
                            'country': country,
                            'partners_with_movement': total_movements,  # Total movements (positive + negative)
                            'net_movement': true_net,  # True net movement (positive + negative scores)
                            'score': data['score']
                        })
                    positive_countries.sort(key=lambda x: x['score'], reverse=True)
                    for i, country_data in enumerate(positive_countries, 1):
                        country_data['rank'] = i

                    # Sort negative countries by score (most negative first)
                    negative_countries = []
                    for country, data in month_data['country_breakdowns']['negative'].items():
                        true_net = true_country_net[country]['positive_score'] + true_country_net[country]['negative_score']
                        total_movements = true_country_net[country]['positive_count'] + true_country_net[country]['negative_count']
                        negative_countries.append({
                            'rank': 0,  # Will be set below
                            'country': country,
                            'partners_with_movement': total_movements,  # Total movements (positive + negative)
                            'net_movement': true_net,  # True net movement (positive + negative scores)
                            'score': data['score']
                        })
                    negative_countries.sort(key=lambda x: x['score'])  # Most negative first
                    for i, country_data in enumerate(negative_countries, 1):
                        country_data['rank'] = i

                    monthly_summary['country_breakdowns'] = {
                        'positive': positive_countries,
                        'negative': negative_countries
                    }

                    # Debug logging for country breakdowns
                    print(f"🔍 {month_str}: {len(positive_countries)} positive countries, {len(negative_countries)} negative countries")

                formatted_monthly_data.append(monthly_summary)
                total_positive_score += month_data['positive_score']
                total_negative_score += month_data['negative_score']

            # Calculate overall summary
            total_weighted_net_movement = total_positive_score + total_negative_score

            summary = {
                'total_positive_score': total_positive_score,
                'total_negative_score': total_negative_score,
                'weighted_net_movement': total_weighted_net_movement,
                'total_months': len(formatted_monthly_data),
                'avg_monthly_net_movement': total_weighted_net_movement / len(formatted_monthly_data) if formatted_monthly_data else 0
            }

            tier_progression_analytics = {
                'monthly_progression': formatted_monthly_data,
                'summary': summary
            }

            # Debug logging for global requests with country breakdowns
            if is_global:
                total_months_with_breakdowns = sum(1 for month in formatted_monthly_data if 'country_breakdowns' in month)
                print(f"🌍 Global response: {len(formatted_monthly_data)} months, {total_months_with_breakdowns} with country breakdowns")

            return jsonify({
                'success': True,
                'data': tier_progression_analytics,
                'country': country
            })

        except Exception as e:
            logger.error(f"Error getting partner tier progression: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/partner-tier-movement-details', methods=['GET'])
    def get_partner_tier_movement_details():
        """Get detailed partner movement data for a specific month and movement type"""
        try:
            partner_data = get_partner_data()
            if partner_data is None:
                return jsonify({'error': 'No data available'}), 400

            country = request.args.get('country')
            month = request.args.get('month')
            movement_type = request.args.get('movement_type')  # 'positive' or 'negative'
            from_tier = request.args.get('from_tier')
            to_tier = request.args.get('to_tier')

            # Handle URL encoding where + should become spaces
            if country:
                country = country.replace('+', ' ')

            if not country:
                return jsonify({'error': 'Country parameter is required'}), 400

            if not month:
                return jsonify({'error': 'Month parameter is required'}), 400

            if not movement_type or movement_type not in ['positive', 'negative']:
                return jsonify({'error': 'Valid movement_type parameter is required (positive or negative)'}), 400

            # Filter data by country
            filtered_data = partner_data[partner_data['country'] == country].copy()

            if filtered_data.empty:
                return jsonify({
                    'success': True,
                    'data': {
                        'movements': [],
                        'summary': {'total_movements': 0, 'total_score': 0}
                    },
                    'country': country,
                    'month': month,
                    'movement_type': movement_type
                })

            # Use shared tier movement scores
            tier_movement_scores = TIER_MOVEMENT_SCORES

            # Sort data by partner and month to track progression
            filtered_data = filtered_data.sort_values(['partner_id', 'month'])

            # Parse the target month
            target_month = pd.to_datetime(month, format='%b %Y')

            # Find movements for the specific month
            movements = []

            # Group by partner to track their tier changes over time
            for partner_id, partner_data_group in filtered_data.groupby('partner_id'):
                partner_months = partner_data_group.sort_values('month')

                # Track tier changes month over month
                for i in range(1, len(partner_months)):
                    current_month = partner_months.iloc[i]
                    previous_month = partner_months.iloc[i-1]

                    # Check if this is the target month
                    if current_month['month'] == target_month:
                        current_tier = current_month['partner_tier']
                        previous_tier = previous_month['partner_tier']

                        # Calculate tier movement score using specific transition values
                        movement_key = (previous_tier, current_tier)
                        movement_score = tier_movement_scores.get(movement_key, 0)

                        # Apply tier filters if specified
                        tier_filter_match = True
                        if from_tier and from_tier != 'All Tiers' and previous_tier != from_tier:
                            tier_filter_match = False
                        if to_tier and to_tier != 'All Tiers' and current_tier != to_tier:
                            tier_filter_match = False

                        # Filter by movement type and tier filters
                        if tier_filter_match:
                            if movement_type == 'positive' and movement_score > 0:
                                movements.append({
                                    'partner_id': partner_id,
                                    'from_tier': previous_tier,
                                    'to_tier': current_tier,
                                    'movement_score': movement_score
                                })
                            elif movement_type == 'negative' and movement_score < 0:
                                movements.append({
                                    'partner_id': partner_id,
                                    'from_tier': previous_tier,
                                    'to_tier': current_tier,
                                    'movement_score': movement_score
                                })

            # Sort movements by score (most negative first for negative, most positive first for positive)
            if movement_type == 'positive':
                movements.sort(key=lambda x: x['movement_score'], reverse=True)
            else:
                movements.sort(key=lambda x: x['movement_score'])

            # Calculate summary
            total_score = sum(movement['movement_score'] for movement in movements)

            summary = {
                'total_movements': len(movements),
                'total_score': total_score,
                'movement_type': movement_type,
                'month': month
            }

            movement_details = {
                'movements': movements,
                'summary': summary
            }

            return jsonify({
                'success': True,
                'data': movement_details,
                'country': country,
                'month': month,
                'movement_type': movement_type
            })

        except Exception as e:
            logger.error(f"Error getting partner tier movement details: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/global-tier-progression-countries', methods=['GET'])
    def get_global_tier_progression_countries():
        """Get country breakdown for global tier progression scores"""
        try:
            partner_data = get_partner_data()
            if partner_data is None:
                return jsonify({'error': 'No data available'}), 400

            # This function always deals with global data
            is_global: bool = True

            month = request.args.get('month')
            movement_type = request.args.get('movement_type')  # 'positive' or 'negative'
            from_tier = request.args.get('from_tier')
            to_tier = request.args.get('to_tier')

            if not month:
                return jsonify({'error': 'Month parameter is required'}), 400

            if not movement_type or movement_type not in ['positive', 'negative']:
                return jsonify({'error': 'Valid movement_type parameter is required (positive or negative)'}), 400

            # Parse the target month string (e.g., "Jul 2025") to datetime
            try:
                month_date = pd.to_datetime(month, format='%b %Y')
            except ValueError:
                return jsonify({'error': f'Invalid month format: {month}. Expected format: "Jul 2025"'}), 400

            # Get all available months in datetime format for finding previous month
            available_months_dt = partner_data['month'].unique()
            available_months_dt = sorted(available_months_dt)

            try:
                current_month_index = list(available_months_dt).index(month_date)
            except ValueError:
                return jsonify({'error': f'Month {month} not found in data'}), 400

            if current_month_index == 0:
                return jsonify({'error': f'No previous month data available for {month}'}), 400

            previous_month_dt = available_months_dt[current_month_index - 1]

            # Get data for current and previous months
            current_month_data = partner_data[partner_data['month'] == month_date]
            previous_month_data = partner_data[partner_data['month'] == previous_month_dt]

            if current_month_data.empty or previous_month_data.empty:
                return jsonify({
                    'success': True,
                    'data': {
                        'countries': [],
                        'total_countries': 0
                    }
                })

            # Use shared tier movement scores
            tier_movement_scores = TIER_MOVEMENT_SCORES

            # Use EXACTLY the same algorithm as main endpoint, but group by country
            # First, run the main algorithm to get all movements for the target month
            month_str = month_date.strftime('%b %Y')
            monthly_progression = {}

            # Run the exact same algorithm as main endpoint
            for partner_id, partner_data_group in partner_data.groupby('partner_id'):
                partner_months = partner_data_group.sort_values('month')

                # Track tier changes month over month
                for i in range(1, len(partner_months)):
                    current_month = partner_months.iloc[i]
                    previous_month = partner_months.iloc[i-1]

                    current_tier = current_month['partner_tier']
                    previous_tier = previous_month['partner_tier']
                    current_month_str = current_month['month'].strftime('%b %Y')

                    # Only process movements that land in our target month
                    if current_month_str != month_str:
                        continue

                    # Apply tier filters if specified
                    tier_filter_match = True
                    if from_tier and from_tier != 'All Tiers' and previous_tier != from_tier:
                        tier_filter_match = False
                    if to_tier and to_tier != 'All Tiers' and current_tier != to_tier:
                        tier_filter_match = False

                    if not tier_filter_match:
                        continue

                    # Calculate tier movement score using specific transition values
                    movement_key = (previous_tier, current_tier)
                    movement_score = tier_movement_scores.get(movement_key, 0)

                    # Initialize month data if not exists
                    if month_str not in monthly_progression:
                        monthly_progression[month_str] = {
                            'positive_movements': 0,
                            'negative_movements': 0,
                            'positive_score': 0,
                            'negative_score': 0,
                            'total_partners_with_movement': 0,
                            'partner_movements': [],
                            # Add country breakdown tracking (always enabled for global requests)
                            'country_breakdowns': {
                                'positive': {},  # {country: {score: X, movement_count: Y}}
                                'negative': {}   # {country: {score: X, movement_count: Y}}
                            }
                        }

                    # Track individual partner movements for country breakdown
                    if movement_score != 0:
                        monthly_progression[month_str]['total_partners_with_movement'] += 1
                        monthly_progression[month_str]['partner_movements'].append({
                            'partner_id': partner_id,
                            'country': current_month['country'],
                            'from_tier': previous_tier,
                            'to_tier': current_tier,
                            'movement_score': movement_score
                        })

                        if movement_score > 0:
                            monthly_progression[month_str]['positive_movements'] += 1
                            monthly_progression[month_str]['positive_score'] += movement_score

                            # Track country breakdown for positive movements (global only)
                            if is_global and monthly_progression[month_str]['country_breakdowns']:
                                country = current_month['country']
                                if pd.notna(country):
                                    if country not in monthly_progression[month_str]['country_breakdowns']['positive']:
                                        monthly_progression[month_str]['country_breakdowns']['positive'][country] = {
                                            'score': 0, 'movement_count': 0
                                        }
                                    monthly_progression[month_str]['country_breakdowns']['positive'][country]['score'] += movement_score
                                    monthly_progression[month_str]['country_breakdowns']['positive'][country]['movement_count'] += 1
                        else:
                            monthly_progression[month_str]['negative_movements'] += 1
                            monthly_progression[month_str]['negative_score'] += movement_score

                            # Track country breakdown for negative movements (global only)
                            if is_global and monthly_progression[month_str]['country_breakdowns']:
                                country = current_month['country']
                                if pd.notna(country):
                                    if country not in monthly_progression[month_str]['country_breakdowns']['negative']:
                                        monthly_progression[month_str]['country_breakdowns']['negative'][country] = {
                                            'score': 0, 'movement_count': 0
                                        }
                                    monthly_progression[month_str]['country_breakdowns']['negative'][country]['score'] += movement_score
                                    monthly_progression[month_str]['country_breakdowns']['negative'][country]['movement_count'] += 1

            # Now group movements by country
            country_scores = {}
            country_total_movements = {}  # Track total movements that passed tier filters

            if month_str in monthly_progression:
                # First pass: count ALL movements that passed tier filters (for Partners with Movement)
                for movement in monthly_progression[month_str]['partner_movements']:
                    country = movement['country']

                    if pd.isna(country):
                        continue

                    if country not in country_total_movements:
                        country_total_movements[country] = 0

                    # Count ALL movements that passed tier filters
                    country_total_movements[country] += 1

                # Second pass: calculate scores for the requested movement type (for ranking)
                for movement in monthly_progression[month_str]['partner_movements']:
                    country = movement['country']
                    movement_score = movement['movement_score']

                    if pd.isna(country):
                        continue

                    # Only include movements of the requested type for scoring/ranking
                    if movement_type == 'positive' and movement_score <= 0:
                        continue
                    if movement_type == 'negative' and movement_score >= 0:
                        continue

                    # Initialize country if not exists
                    if country not in country_scores:
                        country_scores[country] = {
                            'score': 0,
                            'movement_count': 0
                        }

                    country_scores[country]['score'] += movement_score
                    country_scores[country]['movement_count'] += 1

            # Sort countries by score
            if movement_type == 'positive':
                sorted_countries = sorted(country_scores.items(), key=lambda x: x[1]['score'], reverse=True)
            else:
                sorted_countries = sorted(country_scores.items(), key=lambda x: x[1]['score'])

            # Calculate true net movement for each country (considering ALL movements, not just filtered ones)
            true_net_movements = {}
            if month_str in monthly_progression:
                for movement in monthly_progression[month_str]['partner_movements']:
                    country = movement['country']
                    movement_score = movement['movement_score']

                    if pd.isna(country):
                        continue

                    if country not in true_net_movements:
                        true_net_movements[country] = {'positive_score': 0, 'negative_score': 0}

                    if movement_score > 0:
                        true_net_movements[country]['positive_score'] += movement_score
                    elif movement_score < 0:
                        true_net_movements[country]['negative_score'] += movement_score

            # Format response
            countries_list = []
            for i, (country, data) in enumerate(sorted_countries, 1):
                # Calculate true net movement (positive score + negative score)
                country_net_data = true_net_movements.get(country, {'positive_score': 0, 'negative_score': 0})
                true_net_movement = country_net_data['positive_score'] + country_net_data['negative_score']

                # Use total movement count (all movements) instead of filtered count
                total_movements = country_total_movements.get(country, data['movement_count'])

                countries_list.append({
                    'rank': i,
                    'country': country,
                    'partners_with_movement': total_movements,
                    'net_movement': true_net_movement,
                    'score': data['score']
                })

            return jsonify({
                'success': True,
                'data': {
                    'countries': countries_list,
                    'total_countries': len(countries_list)
                }
            })

        except Exception as e:
            logger.error(f"Error getting global tier progression countries: {str(e)}")
            return jsonify({'error': str(e)}), 500