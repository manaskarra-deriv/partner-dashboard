"""
Country Analysis Tab Backend APIs

This module contains all the backend APIs for the Country Analysis tab:
- Partner application funnel (country-only)
- Tier analytics (country-only)
- Country-specific tier analytics
- Tier detail breakdown
- Monthly country funnel data
- Tier performance metrics
- Available countries for applications
"""

from flask import request, jsonify
import logging
import pandas as pd
import numpy as np
from collections import OrderedDict
from db_integration import db
from tier_analytics import get_country_tier_analytics_complete
from utils import validate_partner_data

logger = logging.getLogger(__name__)

def register_country_analysis_routes(app, get_partner_data):
    """Register all country analysis routes"""

    @app.route('/api/partner-application-countries', methods=['GET'])
    def get_partner_application_countries():
        """Get list of countries with partner applications"""
        try:
            countries = db.get_partner_application_countries()
            return jsonify({
                'success': True,
                'countries': countries
            })
        except Exception as e:
            logger.error(f"Error getting partner application countries: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/partner-application-funnel', methods=['GET'])
    def get_partner_application_funnel():
        """Get partner application funnel analytics including monthly trends, activation metrics, and distribution data"""
        try:
            # Get optional filter parameters  
            selected_month = request.args.get('month', 'all')
            countries_param = request.args.get('countries', '')
            
            # Parse countries parameter (comma-separated values)
            selected_countries = []
            if countries_param and countries_param.strip():
                selected_countries = [country.strip() for country in countries_param.split(',') if country.strip()]
            
            # Get application funnel data from Supabase with filters
            funnel_data = db.get_partner_application_funnel_data(selected_month, selected_countries)

            if not funnel_data:
                return jsonify({
                    'monthly_data': [],
                    'country_distribution': [],
                    'summary': {},
                    'error': 'No application funnel data available'
                })
            
            return jsonify({
                'monthly_data': funnel_data.get('monthly_data', []),
                'country_distribution': funnel_data.get('country_distribution', []),
                'summary': funnel_data.get('summary', {}),
                'total_months': len(funnel_data.get('monthly_data', [])),
                'total_countries': len(funnel_data.get('country_distribution', []))
            })

        except Exception as e:
            logger.error(f"Error getting partner application funnel: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/tier-analytics', methods=['GET'])
    def get_tier_analytics():
        """Get comprehensive tier-based analytics"""
        try:
            partner_data = get_partner_data()
            if partner_data is None:
                return jsonify({'error': 'No data available'}), 400
            
            # Get each partner's latest tier for consistent grouping
            partner_latest_tier = partner_data.groupby('partner_id')['partner_tier'].last().reset_index()
            partner_latest_tier.columns = ['partner_id', 'current_tier']
            
            # Merge current tier back to all monthly data for consistent grouping
            monthly_data_with_current_tier = partner_data.merge(partner_latest_tier, on='partner_id')
            
            # Get monthly data by current tier (not historical tier)
            # UPDATED: Only count partners who earned commission that month (total_earnings > 0)
            active_monthly_data = monthly_data_with_current_tier[monthly_data_with_current_tier['total_earnings'] > 0]
            
            monthly_tier_data = active_monthly_data.groupby(['month', 'current_tier']).agg({
                'partner_id': 'nunique',  # Unique partners per tier per month who earned commission
                'total_earnings': 'sum',  # Total earnings per tier per month
                'company_revenue': 'sum',  # Total company revenue per tier per month
                'total_deposits': 'sum',  # Total deposits per tier per month
                'active_clients': 'sum',  # Total active clients per tier per month
                'new_active_clients': 'sum'  # Total new clients per tier per month
            }).reset_index()
            
            # Rename for consistency
            monthly_tier_data = monthly_tier_data.rename(columns={'current_tier': 'partner_tier'})
            
            # Convert month to string for JSON serialization
            monthly_tier_data['month'] = monthly_tier_data['month'].dt.strftime('%Y-%m')
            
            # Get overall totals by tier (using latest tier per partner) - same logic as monthly
            unique_partners = partner_data.groupby('partner_id').agg({
                'partner_tier': 'last',
                'total_earnings': 'sum',
                'company_revenue': 'sum',
                'total_deposits': 'sum',
                'active_clients': 'last',
                'new_active_clients': 'sum'
            }).reset_index()
            
            tier_totals = unique_partners.groupby('partner_tier').agg({
                'partner_id': 'count',
                'total_earnings': 'sum',
                'company_revenue': 'sum',
                'total_deposits': 'sum',
                'active_clients': 'sum',
                'new_active_clients': 'sum'
            }).reset_index()
            
            # UPDATED: Separate active and inactive tiers for calculations
            active_tier_totals = tier_totals[tier_totals['partner_tier'] != 'Inactive']
            
            # Calculate proportions based on ACTIVE tiers only (exclude Inactive from percentage calculations)
            total_earnings = active_tier_totals['total_earnings'].sum()
            total_revenue = active_tier_totals['company_revenue'].sum()
            total_deposits = active_tier_totals['total_deposits'].sum()
            total_active_clients = active_tier_totals['active_clients'].sum()
            total_active_partners = active_tier_totals['partner_id'].sum()
            
            # Format tier totals with proportions
            tier_summary = []
            tier_order = ['Platinum', 'Gold', 'Silver', 'Bronze', 'Inactive']
            
            for tier in tier_order:
                tier_data = tier_totals[tier_totals['partner_tier'] == tier]
                if not tier_data.empty:
                    row = tier_data.iloc[0]
                    
                    # UPDATED: Handle Inactive tier separately (show 0% for all percentages)
                    if tier == 'Inactive':
                        tier_summary.append({
                            'tier': tier,
                            'partner_count': int(row['partner_id']),
                            'total_earnings': float(row['total_earnings']),
                            'total_revenue': float(row['company_revenue']),
                            'total_deposits': float(row['total_deposits']),
                            'active_clients': int(row['active_clients']),
                            'new_clients': int(row['new_active_clients']),
                            'earnings_percentage': 0.0,  # Always 0% for Inactive
                            'revenue_percentage': 0.0,   # Always 0% for Inactive
                            'deposits_percentage': 0.0,  # Always 0% for Inactive
                            'clients_percentage': 0.0,   # Always 0% for Inactive  
                            'partner_percentage': 0.0    # Always 0% for Inactive
                        })
                    else:
                        tier_summary.append({
                            'tier': tier,
                            'partner_count': int(row['partner_id']),
                            'total_earnings': float(row['total_earnings']),
                            'total_revenue': float(row['company_revenue']),
                            'total_deposits': float(row['total_deposits']),
                            'active_clients': int(row['active_clients']),
                            'new_clients': int(row['new_active_clients']),
                            'earnings_percentage': float(row['total_earnings'] / total_earnings * 100) if total_earnings > 0 else 0,
                            'revenue_percentage': float(row['company_revenue'] / total_revenue * 100) if total_revenue > 0 else 0,
                            'deposits_percentage': float(row['total_deposits'] / total_deposits * 100) if total_deposits > 0 else 0,
                            'clients_percentage': float(row['active_clients'] / total_active_clients * 100) if total_active_clients > 0 else 0,
                            'partner_percentage': float(row['partner_id'] / total_active_partners * 100) if total_active_partners > 0 else 0
                        })
            
            # Format monthly data for charts (include all tiers including Inactive)
            months = sorted(monthly_tier_data['month'].unique())
            monthly_charts = {}
            
            for metric in ['total_earnings', 'company_revenue', 'total_deposits', 'partner_id', 'active_clients', 'new_active_clients']:
                monthly_charts[metric] = []
                for month in months:
                    month_data = {'month': month}
                    for tier in tier_order:
                        tier_month_data = monthly_tier_data[
                            (monthly_tier_data['month'] == month) & 
                            (monthly_tier_data['partner_tier'] == tier)
                        ]
                        if not tier_month_data.empty:
                            month_data[tier.lower()] = float(tier_month_data.iloc[0][metric])
                        else:
                            month_data[tier.lower()] = 0
                    monthly_charts[metric].append(month_data)
            
            # UPDATED: Use total from all partners (including Inactive) for total count, but active totals for financial metrics
            total_all_partners = tier_totals['partner_id'].sum()
            
            analytics_data = {
                'tier_summary': tier_summary,
                'monthly_charts': monthly_charts,
                'totals': {
                    'total_partners': int(total_all_partners),      # Include all partners
                    'total_earnings': float(total_earnings),        # Active partners only
                    'total_revenue': float(total_revenue),          # Active partners only
                    'total_deposits': float(total_deposits),        # Active partners only
                    'total_active_clients': int(total_active_clients)  # Active partners only
                }
            }
            
            return jsonify(analytics_data)
            
        except Exception as e:
            logger.error(f"Error getting tier analytics: {str(e)}")
            return jsonify({'error': str(e)}), 500

    # Register the complete country tier analytics with full ranking calculations
    get_country_tier_analytics_complete(app, get_partner_data)

    @app.route('/api/tier-detail', methods=['GET'])
    def get_tier_detail():
        """Get detailed breakdown for a specific tier and country"""
        try:
            tier = request.args.get('tier')
            country = request.args.get('country')
            month = request.args.get('month')

            if not country:
                return jsonify({'error': 'Country parameter is required'}), 400

            tier_data = db.get_tier_detail_data(
                tier=tier,
                country=country,
                month=month
            )

            return jsonify({
                'success': True,
                'data': tier_data,
                'tier': tier,
                'country': country,
                'month': month
            })

        except Exception as e:
            logger.error(f"Error getting tier detail: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/monthly-country-funnel', methods=['GET'])
    def get_monthly_country_funnel():
        """Get monthly funnel data for a specific country with rankings"""
        try:
            country = request.args.get('country')

            # Handle URL encoding where + should become spaces
            if country:
                country = country.replace('+', ' ')

            if not country:
                return jsonify({'error': 'Country parameter is required'}), 400

            funnel_data = db.get_monthly_country_funnel_data(country=country)

            return jsonify({
                'success': True,
                'data': funnel_data,
                'country': country
            })

        except Exception as e:
            logger.error(f"Error getting monthly country funnel: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/tier-performance', methods=['GET'])
    def get_tier_performance():
        """Get detailed tier performance data with rankings for a specific tier and country"""
        try:
            partner_data = get_partner_data()
            if partner_data is None:
                return jsonify({'error': 'No data available'}), 400

            country = request.args.get('country')
            tier = request.args.get('tier')

            if not country:
                return jsonify({'error': 'Country parameter is required'}), 400

            if not tier:
                return jsonify({'error': 'Tier parameter is required'}), 400

            # Filter CSV data by country and tier
            filtered_data = partner_data.copy()

            if country:
                filtered_data = filtered_data[filtered_data['country'] == country]

            # Filter by partners who have the specified tier (latest tier)
            partner_latest_tier = filtered_data.groupby('partner_id')['partner_tier'].last().reset_index()
            tier_partners = partner_latest_tier[partner_latest_tier['partner_tier'] == tier]['partner_id'].tolist()

            if not tier_partners:
                return jsonify({
                    'success': True,
                    'data': [],
                    'tier': tier,
                    'country': country
                })

            # Get data only for partners with this tier
            tier_filtered_data = filtered_data[filtered_data['partner_id'].isin(tier_partners)]

            # Get monthly performance for these partners
            monthly_performance = tier_filtered_data.groupby('month').agg({
                'partner_id': 'nunique',
                'total_earnings': 'sum',
                'company_revenue': 'sum',
                'total_deposits': 'sum',
                'active_clients': 'sum',
                'new_active_clients': 'sum',
                'volume_usd': 'sum'
            }).reset_index()

            # Calculate EtR and EtD ratios
            monthly_performance['etr_ratio'] = monthly_performance.apply(
                lambda row: round((row['total_earnings'] / row['company_revenue'] * 100), 2)
                if row['company_revenue'] > 0 else 0, axis=1
            )
            monthly_performance['etd_ratio'] = monthly_performance.apply(
                lambda row: round((row['total_earnings'] / row['total_deposits'] * 100), 2)
                if row['total_deposits'] > 0 else 0, axis=1
            )

            # Now calculate rankings compared to ALL countries for this tier
            # Get all countries' data for this tier to calculate rankings
            all_countries_tier_data = []

            for compare_country in partner_data['country'].unique():
                if pd.isna(compare_country):
                    continue

                country_data = partner_data[partner_data['country'] == compare_country]
                country_partner_tiers = country_data.groupby('partner_id')['partner_tier'].last().reset_index()
                country_tier_partners = country_partner_tiers[country_partner_tiers['partner_tier'] == tier]['partner_id'].tolist()

                if not country_tier_partners:
                    continue

                country_tier_data = country_data[country_data['partner_id'].isin(country_tier_partners)]

                country_monthly = country_tier_data.groupby('month').agg({
                    'total_earnings': 'sum',
                    'company_revenue': 'sum',
                    'total_deposits': 'sum',
                    'active_clients': 'sum',
                    'new_active_clients': 'sum',
                    'volume_usd': 'sum'
                }).reset_index()

                for _, row in country_monthly.iterrows():
                    all_countries_tier_data.append({
                        'country': compare_country,
                        'month': row['month'],
                        'total_earnings': row['total_earnings'],
                        'company_revenue': row['company_revenue'],
                        'total_deposits': row['total_deposits'],
                        'active_clients': row['active_clients'],
                        'new_active_clients': row['new_active_clients'],
                        'volume_usd': row['volume_usd']
                    })

            # Convert to DataFrame for ranking calculations
            all_countries_df = pd.DataFrame(all_countries_tier_data)

            # Sort monthly performance by month descending
            monthly_performance = monthly_performance.sort_values('month', ascending=False)

            # Calculate rankings for each month
            formatted_results = []
            for _, row in monthly_performance.iterrows():
                month_str = row['month'].strftime('%b %Y')

                # Get rankings for this month across all countries
                month_data = all_countries_df[all_countries_df['month'] == row['month']]

                if not month_data.empty:
                    # Calculate rankings (lower rank = better performance)
                    month_data_sorted = month_data.copy()
                    month_data_sorted['earnings_rank'] = month_data_sorted['total_earnings'].rank(method='dense', ascending=False)
                    month_data_sorted['revenue_rank'] = month_data_sorted['company_revenue'].rank(method='dense', ascending=False)
                    month_data_sorted['deposits_rank'] = month_data_sorted['total_deposits'].rank(method='dense', ascending=False)
                    month_data_sorted['clients_rank'] = month_data_sorted['active_clients'].rank(method='dense', ascending=False)
                    month_data_sorted['new_clients_rank'] = month_data_sorted['new_active_clients'].rank(method='dense', ascending=False)
                    month_data_sorted['volume_rank'] = month_data_sorted['volume_usd'].rank(method='dense', ascending=False)

                    # Find current country's ranking
                    current_country_rank = month_data_sorted[month_data_sorted['country'] == country]

                    if not current_country_rank.empty:
                        rank_data = current_country_rank.iloc[0]
                        earnings_rank = int(rank_data['earnings_rank'])
                        revenue_rank = int(rank_data['revenue_rank'])
                        deposits_rank = int(rank_data['deposits_rank'])
                        clients_rank = int(rank_data['clients_rank'])
                        new_clients_rank = int(rank_data['new_clients_rank'])
                        volume_rank = int(rank_data['volume_rank'])
                    else:
                        # Fallback rankings
                        earnings_rank = revenue_rank = deposits_rank = clients_rank = new_clients_rank = volume_rank = 1
                else:
                    # Fallback rankings
                    earnings_rank = revenue_rank = deposits_rank = clients_rank = new_clients_rank = volume_rank = 1

                formatted_results.append({
                    'month': month_str,
                    'tier': tier,
                    'total_earnings': float(row['total_earnings']),
                    'earnings_rank': earnings_rank,
                    'company_revenue': float(row['company_revenue']),
                    'revenue_rank': revenue_rank,
                    'etr_ratio': float(row['etr_ratio']),
                    'total_deposits': float(row['total_deposits']),
                    'deposits_rank': deposits_rank,
                    'etd_ratio': float(row['etd_ratio']),
                    'active_clients': int(row['active_clients']),
                    'clients_rank': clients_rank,
                    'new_clients': int(row['new_active_clients']),
                    'new_clients_rank': new_clients_rank,
                    'volume': float(row['volume_usd']),
                    'volume_rank': volume_rank
                })

            return jsonify({
                'success': True,
                'data': formatted_results,
                'tier': tier,
                'country': country,
                'total_months': len(formatted_results)
            })

        except Exception as e:
            logger.error(f"Error getting tier performance data: {str(e)}")
            return jsonify({'error': str(e)}), 500