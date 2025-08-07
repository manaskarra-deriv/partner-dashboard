"""
Complete Country Tier Analytics with Full Ranking Calculations

This module contains the EXACT, COMPLETE implementation of the massive
get_country_tier_analytics function from the original main.py with ALL
the complex ranking calculations preserved exactly as-is.

NOTE: Region functionality has been removed - this now only supports country analysis.
"""

from flask import request, jsonify
import logging
import pandas as pd
import numpy as np
from collections import OrderedDict

logger = logging.getLogger(__name__)

def get_country_tier_analytics_complete(app, get_partner_data):
    """Register the complete country tier analytics route with full ranking calculations"""

    @app.route('/api/country-tier-analytics', methods=['GET'])
    def get_country_tier_analytics():
        """Get comprehensive tier analytics for a specific country using CSV data"""
        try:
            partner_data = get_partner_data()
            if partner_data is None:
                return jsonify({'error': 'No data available'}), 400

            country = request.args.get('country')
            include_rankings = request.args.get('include_rankings', 'false').lower() == 'true'

            print(f"🔍 Country tier analytics request: country={country}, include_rankings={include_rankings}")

            # Handle URL encoding where + should become spaces
            if country:
                country = country.replace('+', ' ')

            if not country:
                return jsonify({'error': 'Country parameter is required'}), 400

            # Filter CSV data by country
            filtered_data = partner_data[partner_data['country'] == country].copy()

            if filtered_data.empty:
                return jsonify({
                    'success': True,
                    'data': {
                        'summary': {},
                        'monthly_tier_data': {},
                        'country_rankings': {},
                        'available_months': []
                    },
                    'country': country
                })

            # Get each partner's latest tier for consistent grouping
            partner_latest_tier = filtered_data.groupby('partner_id')['partner_tier'].last().reset_index()
            partner_latest_tier.columns = ['partner_id', 'current_tier']

            # Merge current tier back to all monthly data for consistent grouping
            monthly_data_with_current_tier = filtered_data.merge(partner_latest_tier, on='partner_id')

            # Get monthly data by current tier
            monthly_tier_data = monthly_data_with_current_tier.groupby(['month', 'current_tier']).agg({
                'partner_id': 'nunique',
                'total_earnings': 'sum',
                'company_revenue': 'sum',
                'total_deposits': 'sum',
                'active_clients': 'sum',
                'new_active_clients': 'sum',
                'volume_usd': 'sum'
            }).reset_index()

            # Rename for consistency
            monthly_tier_data = monthly_tier_data.rename(columns={'current_tier': 'partner_tier'})

            # Sort by month descending first (latest to earliest) and keep original date for sorting
            monthly_tier_data = monthly_tier_data.sort_values('month', ascending=False)

            # Create a month sorting reference before converting to string
            month_order = monthly_tier_data['month'].dt.to_period('M').drop_duplicates().sort_values(ascending=False)
            month_order_list = [period.strftime('%b %Y') for period in month_order]

            # Convert month to string for JSON serialization
            monthly_tier_data['month'] = monthly_tier_data['month'].dt.strftime('%b %Y')

            # Get overall totals by tier
            unique_partners = filtered_data.groupby('partner_id').agg({
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

            # Calculate overall summary
            total_partners = tier_totals['partner_id'].sum()
            # Calculate active partners (excluding Inactive tier)
            active_tier_totals = tier_totals[tier_totals['partner_tier'] != 'Inactive']
            total_active_partners = active_tier_totals['partner_id'].sum()
            total_earnings = tier_totals['total_earnings'].sum()
            total_company_revenue = tier_totals['company_revenue'].sum()
            total_deposits = tier_totals['total_deposits'].sum()
            total_clients = tier_totals['active_clients'].sum()

            # Format monthly tier data for frontend (preserve chronological order)
            from collections import OrderedDict
            monthly_data = OrderedDict()

            # Process in chronological order (latest first)
            for month_str in month_order_list:
                monthly_data[month_str] = {}

            # Fill in the tier data (initially without rankings)
            for _, row in monthly_tier_data.iterrows():
                month_str = row['month']
                tier = row['partner_tier']
                monthly_data[month_str][tier] = {
                    'count': int(row['partner_id']),
                    'earnings': float(row['total_earnings']),
                    'revenue': float(row['company_revenue']),
                    'deposits': float(row['total_deposits']),
                    'active_clients': int(row['active_clients']),
                    'new_clients': int(row['new_active_clients']),
                    'volume': float(row['volume_usd'])
                }

            # Fast mode: return basic data without expensive ranking calculations
            if not include_rankings:
                print("🚀 Fast mode: Returning basic data without rankings")

                # Create summary without rankings (all ranks default to 1)
                summary = {
                    'partner_country': country,
                    'total_partners': int(total_partners),
                    'total_active_partners': int(total_active_partners),
                    'total_company_revenue': float(total_company_revenue),
                    'total_partner_earnings': float(total_earnings),
                    'total_deposits': float(total_deposits),
                    'total_new_clients': int(total_clients),
                    'partners_rank': 1,
                    'active_partners_rank': 1,
                    'revenue_rank': 1,
                    'earnings_rank': 1,
                    'deposits_rank': 1,
                    'clients_rank': 1,
                    'etr_rank': 1,
                    'etd_rank': 1,
                    'avg_monthly_revenue_rank': 1,
                    'avg_monthly_earnings_rank': 1,
                    'avg_monthly_deposits_rank': 1,
                    'avg_monthly_new_clients_rank': 1
                }

                analytics_data = {
                    'summary': summary,
                    'monthly_tier_data': monthly_data,
                    'tier_country_rankings': {},
                    'monthly_rankings': {},
                    'tier_monthly_rankings': {},
                    'country_rankings': {},
                    'available_months': list(monthly_data.keys()) if monthly_data else [],
                    'global_totals': {}
                }

                return jsonify({
                    'success': True,
                    'data': analytics_data,
                    'country': country
                })

            # Calculate real rankings by comparing against all countries
            try:
                # Get all countries' data for comparison
                all_countries_data = []
                for compare_country in partner_data['country'].unique():
                    if pd.isna(compare_country):
                        continue

                    country_data = partner_data[partner_data['country'] == compare_country]

                    # Calculate active partners for this country (excluding Inactive tier)
                    country_partner_tiers = country_data.groupby('partner_id')['partner_tier'].last().reset_index()
                    active_partners_count = len(country_partner_tiers[country_partner_tiers['partner_tier'] != 'Inactive'])

                    # Aggregate country metrics
                    country_totals = country_data.groupby('partner_id').agg({
                        'total_earnings': 'sum',
                        'company_revenue': 'sum',
                        'total_deposits': 'sum',
                        'active_clients': 'last',
                        'new_active_clients': 'sum'
                    }).sum()

                    all_countries_data.append({
                        'country': compare_country,
                        'partner_id': len(country_data['partner_id'].unique()),
                        'active_partners': active_partners_count,
                        'total_earnings': country_totals['total_earnings'],
                        'company_revenue': country_totals['company_revenue'],
                        'total_deposits': country_totals['total_deposits'],
                        'active_clients': country_totals['active_clients'],
                        'new_active_clients': country_totals['new_active_clients']
                    })

                all_countries_df = pd.DataFrame(all_countries_data)

                # Calculate ETR and ETD ratios for each country
                all_countries_df['etr_ratio'] = np.where(
                    all_countries_df['company_revenue'] > 0,
                    (all_countries_df['total_earnings'] / all_countries_df['company_revenue']) * 100,
                    0
                )
                all_countries_df['etd_ratio'] = np.where(
                    all_countries_df['total_deposits'] > 0,
                    (all_countries_df['total_earnings'] / all_countries_df['total_deposits']) * 100,
                    0
                )

                # Calculate rankings for countries
                all_countries_df['earnings_rank'] = all_countries_df['total_earnings'].rank(method='dense', ascending=False)
                all_countries_df['revenue_rank'] = all_countries_df['company_revenue'].rank(method='dense', ascending=False)
                all_countries_df['deposits_rank'] = all_countries_df['total_deposits'].rank(method='dense', ascending=False)
                all_countries_df['clients_rank'] = all_countries_df['active_clients'].rank(method='dense', ascending=False)
                all_countries_df['partners_rank'] = all_countries_df['partner_id'].rank(method='dense', ascending=False)
                all_countries_df['active_partners_rank'] = all_countries_df['active_partners'].rank(method='dense', ascending=False)
                all_countries_df['etr_rank'] = all_countries_df['etr_ratio'].rank(method='dense', ascending=False)
                all_countries_df['etd_rank'] = all_countries_df['etd_ratio'].rank(method='dense', ascending=False)

                # Calculate monthly averages for ranking
                months_count = len(month_order_list)
                all_countries_df['avg_monthly_revenue'] = all_countries_df['company_revenue'] / months_count if months_count > 0 else 0
                all_countries_df['avg_monthly_earnings'] = all_countries_df['total_earnings'] / months_count if months_count > 0 else 0
                all_countries_df['avg_monthly_deposits'] = all_countries_df['total_deposits'] / months_count if months_count > 0 else 0
                all_countries_df['avg_monthly_new_clients'] = all_countries_df['new_active_clients'] / months_count if months_count > 0 else 0

                all_countries_df['avg_monthly_revenue_rank'] = all_countries_df['avg_monthly_revenue'].rank(method='dense', ascending=False)
                all_countries_df['avg_monthly_earnings_rank'] = all_countries_df['avg_monthly_earnings'].rank(method='dense', ascending=False)
                all_countries_df['avg_monthly_deposits_rank'] = all_countries_df['avg_monthly_deposits'].rank(method='dense', ascending=False)
                all_countries_df['avg_monthly_new_clients_rank'] = all_countries_df['avg_monthly_new_clients'].rank(method='dense', ascending=False)

                # Find current country's rankings
                current_country_data = all_countries_df[all_countries_df['country'] == country]
                if not current_country_data.empty:
                    country_rank_data = current_country_data.iloc[0]
                    summary = {
                        'partner_country': country,
                        'total_partners': int(total_partners),
                        'total_active_partners': int(total_active_partners),
                        'total_company_revenue': float(total_company_revenue),
                        'total_partner_earnings': float(total_earnings),
                        'total_deposits': float(total_deposits),
                        'total_new_clients': int(total_clients),
                        'partners_rank': int(country_rank_data['partners_rank']),
                        'active_partners_rank': int(country_rank_data['active_partners_rank']),
                        'revenue_rank': int(country_rank_data['revenue_rank']),
                        'earnings_rank': int(country_rank_data['earnings_rank']),
                        'deposits_rank': int(country_rank_data['deposits_rank']),
                        'clients_rank': int(country_rank_data['clients_rank']),
                        'etr_rank': int(country_rank_data['etr_rank']),
                        'etd_rank': int(country_rank_data['etd_rank']),
                        'avg_monthly_revenue_rank': int(country_rank_data['avg_monthly_revenue_rank']),
                        'avg_monthly_earnings_rank': int(country_rank_data['avg_monthly_earnings_rank']),
                        'avg_monthly_deposits_rank': int(country_rank_data['avg_monthly_deposits_rank']),
                        'avg_monthly_new_clients_rank': int(country_rank_data['avg_monthly_new_clients_rank'])
                    }
                else:
                    # Fallback summary with rank 1 for all metrics
                    summary = {
                        'partner_country': country,
                        'total_partners': int(total_partners),
                        'total_active_partners': int(total_active_partners),
                        'total_company_revenue': float(total_company_revenue),
                        'total_partner_earnings': float(total_earnings),
                        'total_deposits': float(total_deposits),
                        'total_new_clients': int(total_clients),
                        'partners_rank': 1,
                        'active_partners_rank': 1,
                        'revenue_rank': 1,
                        'earnings_rank': 1,
                        'deposits_rank': 1,
                        'clients_rank': 1,
                        'etr_rank': 1,
                        'etd_rank': 1,
                        'avg_monthly_revenue_rank': 1,
                        'avg_monthly_earnings_rank': 1,
                        'avg_monthly_deposits_rank': 1,
                        'avg_monthly_new_clients_rank': 1
                    }

            except Exception as e:
                logger.error(f"Error calculating country rankings: {str(e)}")
                # Fallback summary with rank 1 for all metrics
                summary = {
                    'partner_country': country,
                    'total_partners': int(total_partners),
                    'total_active_partners': int(total_active_partners),
                    'total_company_revenue': float(total_company_revenue),
                    'total_partner_earnings': float(total_earnings),
                    'total_deposits': float(total_deposits),
                    'total_new_clients': int(total_clients),
                    'partners_rank': 1,
                    'active_partners_rank': 1,
                    'revenue_rank': 1,
                    'earnings_rank': 1,
                    'deposits_rank': 1,
                    'clients_rank': 1,
                    'etr_rank': 1,
                    'etd_rank': 1,
                    'avg_monthly_revenue_rank': 1,
                    'avg_monthly_earnings_rank': 1,
                    'avg_monthly_deposits_rank': 1,
                    'avg_monthly_new_clients_rank': 1
                }

            # Calculate tier-specific country rankings
            tier_country_rankings = {}
            monthly_rankings = {}
            tier_monthly_rankings = {}

            # Calculate tier-specific rankings for each tier
            tiers = ['Platinum', 'Gold', 'Silver', 'Bronze', 'Inactive']
            for tier in tiers:
                tier_country_rankings[tier] = {}
                tier_monthly_rankings[tier] = {}

            # Calculate tier-specific country rankings (overall, not monthly)
            for tier in tiers:
                try:
                    # Get all countries' data for this specific tier
                    tier_countries_data = []
                    all_countries = partner_data['country'].unique()
                    
                    for other_country in all_countries:
                        if pd.isna(other_country):
                            continue
                        
                        country_data = partner_data[partner_data['country'] == other_country]
                        # Get partners of this tier for this country
                        country_partner_tiers = country_data.groupby('partner_id')['partner_tier'].last().reset_index()
                        tier_partners = country_partner_tiers[country_partner_tiers['partner_tier'] == tier]['partner_id'].tolist()
                        
                        if tier_partners:
                            tier_data = country_data[country_data['partner_id'].isin(tier_partners)]
                            tier_totals = tier_data.agg({
                                'total_earnings': 'sum',
                                'company_revenue': 'sum',
                                'total_deposits': 'sum',
                                'active_clients': 'sum',
                                'new_active_clients': 'sum',
                                'volume_usd': 'sum',
                                'partner_id': 'nunique'
                            })
                            
                            etr_ratio = (tier_totals['total_earnings'] / tier_totals['company_revenue'] * 100) if tier_totals['company_revenue'] > 0 else 0
                            etd_ratio = (tier_totals['total_earnings'] / tier_totals['total_deposits'] * 100) if tier_totals['total_deposits'] > 0 else 0
                            
                            tier_countries_data.append({
                                'country': other_country,
                                'partners_count': tier_totals['partner_id'],
                                'earnings': tier_totals['total_earnings'],
                                'revenue': tier_totals['company_revenue'],
                                'deposits': tier_totals['total_deposits'],
                                'active_clients': tier_totals['active_clients'],
                                'new_clients': tier_totals['new_active_clients'],
                                'volume': tier_totals['volume_usd'],
                                'etr_ratio': etr_ratio,
                                'etd_ratio': etd_ratio
                            })
                        else:
                            # Country has 0 partners in this tier
                            tier_countries_data.append({
                                'country': other_country,
                                'partners_count': 0,
                                'earnings': 0.0,
                                'revenue': 0.0,
                                'deposits': 0.0,
                                'active_clients': 0,
                                'new_clients': 0,
                                'volume': 0.0,
                                'etr_ratio': 0.0,
                                'etd_ratio': 0.0
                            })
                    
                    if tier_countries_data:
                        tier_df = pd.DataFrame(tier_countries_data)
                        tier_df['partners_rank'] = tier_df['partners_count'].rank(method='dense', ascending=False)
                        tier_df['earnings_rank'] = tier_df['earnings'].rank(method='dense', ascending=False)
                        tier_df['revenue_rank'] = tier_df['revenue'].rank(method='dense', ascending=False)
                        tier_df['deposits_rank'] = tier_df['deposits'].rank(method='dense', ascending=False)
                        tier_df['active_clients_rank'] = tier_df['active_clients'].rank(method='dense', ascending=False)
                        tier_df['new_clients_rank'] = tier_df['new_clients'].rank(method='dense', ascending=False)
                        tier_df['volume_rank'] = tier_df['volume'].rank(method='dense', ascending=False)
                        tier_df['etr_rank'] = tier_df['etr_ratio'].rank(method='dense', ascending=False)
                        tier_df['etd_rank'] = tier_df['etd_ratio'].rank(method='dense', ascending=False)
                        
                        # Get current country's ranking for this tier
                        current_tier_data = tier_df[tier_df['country'] == country]
                        if not current_tier_data.empty:
                            tier_country_rankings[tier] = {
                                'partners_rank': int(current_tier_data.iloc[0]['partners_rank']),
                                'earnings_rank': int(current_tier_data.iloc[0]['earnings_rank']),
                                'revenue_rank': int(current_tier_data.iloc[0]['revenue_rank']),
                                'deposits_rank': int(current_tier_data.iloc[0]['deposits_rank']),
                                'active_clients_rank': int(current_tier_data.iloc[0]['active_clients_rank']),
                                'new_clients_rank': int(current_tier_data.iloc[0]['new_clients_rank']),
                                'volume_rank': int(current_tier_data.iloc[0]['volume_rank']),
                                'etr_rank': int(current_tier_data.iloc[0]['etr_rank']),
                                'etd_rank': int(current_tier_data.iloc[0]['etd_rank'])
                            }
                        else:
                            # Country has no data for this tier
                            tier_country_rankings[tier] = {}
                    else:
                        tier_country_rankings[tier] = {}
                        
                except Exception as e:
                    logger.error(f"Error calculating tier country rankings for {tier}: {str(e)}")
                    tier_country_rankings[tier] = {}

            # Calculate monthly rankings and tier-specific monthly rankings
            for month_str in month_order_list:
                # Get all data for this month to calculate rankings
                try:
                    month_date = pd.to_datetime(month_str, format='%b %Y')
                    month_data_all = partner_data[partner_data['month'] == month_date]

                    if not month_data_all.empty:
                        # Calculate global monthly rankings (for Monthly Totals table)
                        # Compare current country's total performance vs all other countries
                        countries_month_data = []
                        all_countries = month_data_all['country'].unique()
                        
                        for other_country in all_countries:
                            if pd.isna(other_country):
                                continue
                            
                            country_month_data = month_data_all[month_data_all['country'] == other_country]
                            country_month_totals = country_month_data.agg({
                                'total_earnings': 'sum',
                                'company_revenue': 'sum', 
                                'total_deposits': 'sum',
                                'active_clients': 'sum',
                                'new_active_clients': 'sum',
                                'volume_usd': 'sum',
                                'partner_id': 'nunique'
                            })
                            
                            countries_month_data.append({
                                'country': other_country,
                                'partners_count': country_month_totals['partner_id'],
                                'earnings': country_month_totals['total_earnings'],
                                'revenue': country_month_totals['company_revenue'],
                                'deposits': country_month_totals['total_deposits'],
                                'active_clients': country_month_totals['active_clients'],
                                'new_clients': country_month_totals['new_active_clients'],
                                'volume': country_month_totals['volume_usd']
                            })
                        
                        if countries_month_data:
                            countries_df = pd.DataFrame(countries_month_data)
                            countries_df['partners_rank'] = countries_df['partners_count'].rank(method='dense', ascending=False)
                            countries_df['earnings_rank'] = countries_df['earnings'].rank(method='dense', ascending=False)
                            countries_df['revenue_rank'] = countries_df['revenue'].rank(method='dense', ascending=False)
                            countries_df['deposits_rank'] = countries_df['deposits'].rank(method='dense', ascending=False)
                            countries_df['active_clients_rank'] = countries_df['active_clients'].rank(method='dense', ascending=False)
                            countries_df['new_clients_rank'] = countries_df['new_clients'].rank(method='dense', ascending=False)
                            countries_df['volume_rank'] = countries_df['volume'].rank(method='dense', ascending=False)
                            
                            # Get current country's ranking
                            current_country_data = countries_df[countries_df['country'] == country]
                            if not current_country_data.empty:
                                monthly_rankings[month_str] = {
                                    'partners_rank': int(current_country_data.iloc[0]['partners_rank']),
                                    'earnings_rank': int(current_country_data.iloc[0]['earnings_rank']),
                                    'revenue_rank': int(current_country_data.iloc[0]['revenue_rank']),
                                    'deposits_rank': int(current_country_data.iloc[0]['deposits_rank']),
                                    'active_clients_rank': int(current_country_data.iloc[0]['active_clients_rank']),
                                    'new_clients_rank': int(current_country_data.iloc[0]['new_clients_rank']),
                                    'volume_rank': int(current_country_data.iloc[0]['volume_rank'])
                                }
                            else:
                                monthly_rankings[month_str] = {
                                    'partners_rank': 1,
                                    'earnings_rank': 1,
                                    'revenue_rank': 1,
                                    'deposits_rank': 1,
                                    'active_clients_rank': 1,
                                    'new_clients_rank': 1,
                                    'volume_rank': 1
                                }
                        else:
                            monthly_rankings[month_str] = {
                                'partners_rank': 1,
                                'earnings_rank': 1,
                                'revenue_rank': 1,
                                'deposits_rank': 1,
                                'active_clients_rank': 1,
                                'new_clients_rank': 1,
                                'volume_rank': 1
                            }
                        # Calculate monthly rankings for each tier
                        for tier in tiers:
                            tier_monthly_rankings[tier][month_str] = {
                                'partners_rank': 1,
                                'earnings_rank': 1,
                                'revenue_rank': 1,
                                'deposits_rank': 1,
                                'active_clients_rank': 1,
                                'new_clients_rank': 1,
                                'volume_rank': 1,
                                'etr_rank': 1,
                                'etd_rank': 1
                            }

                            # For countries: tier-specific country vs country rankings logic
                            tier_countries_month_data = []
                            all_countries = month_data_all['country'].unique()

                            for other_country in all_countries:
                                if pd.isna(other_country):
                                    continue

                                country_month_data = month_data_all[month_data_all['country'] == other_country]
                                # Get partners of this tier for this country in this month
                                country_partner_tiers = country_month_data.groupby('partner_id')['partner_tier'].last().reset_index()
                                tier_partners = country_partner_tiers[country_partner_tiers['partner_tier'] == tier]['partner_id'].tolist()

                                if tier_partners:
                                    tier_month_data = country_month_data[country_month_data['partner_id'].isin(tier_partners)]
                                    tier_month_totals = tier_month_data.agg({
                                        'total_earnings': 'sum',
                                        'company_revenue': 'sum',
                                        'total_deposits': 'sum',
                                        'active_clients': 'sum',
                                        'new_active_clients': 'sum',
                                        'volume_usd': 'sum',
                                        'partner_id': 'nunique'
                                    })

                                    etr_ratio = (tier_month_totals['total_earnings'] / tier_month_totals['company_revenue'] * 100) if tier_month_totals['company_revenue'] > 0 else 0
                                    etd_ratio = (tier_month_totals['total_earnings'] / tier_month_totals['total_deposits'] * 100) if tier_month_totals['total_deposits'] > 0 else 0

                                    tier_countries_month_data.append({
                                        'country': other_country,
                                        'partners_count': tier_month_totals['partner_id'],
                                        'earnings': tier_month_totals['total_earnings'],
                                        'revenue': tier_month_totals['company_revenue'],
                                        'deposits': tier_month_totals['total_deposits'],
                                        'active_clients': tier_month_totals['active_clients'],
                                        'new_clients': tier_month_totals['new_active_clients'],
                                        'volume': tier_month_totals['volume_usd'],
                                        'etr_ratio': etr_ratio,
                                        'etd_ratio': etd_ratio
                                    })
                                else:
                                    # Country has 0 partners in this tier for this month
                                    tier_countries_month_data.append({
                                        'country': other_country,
                                        'partners_count': 0,
                                        'earnings': 0.0,
                                        'revenue': 0.0,
                                        'deposits': 0.0,
                                        'active_clients': 0,
                                        'new_clients': 0,
                                        'volume': 0.0,
                                        'etr_ratio': 0.0,
                                        'etd_ratio': 0.0
                                    })

                            if tier_countries_month_data:
                                tier_month_df = pd.DataFrame(tier_countries_month_data)
                                tier_month_df['partners_rank'] = tier_month_df['partners_count'].rank(method='dense', ascending=False)
                                tier_month_df['earnings_rank'] = tier_month_df['earnings'].rank(method='dense', ascending=False)
                                tier_month_df['revenue_rank'] = tier_month_df['revenue'].rank(method='dense', ascending=False)
                                tier_month_df['deposits_rank'] = tier_month_df['deposits'].rank(method='dense', ascending=False)
                                tier_month_df['active_clients_rank'] = tier_month_df['active_clients'].rank(method='dense', ascending=False)
                                tier_month_df['new_clients_rank'] = tier_month_df['new_clients'].rank(method='dense', ascending=False)
                                tier_month_df['volume_rank'] = tier_month_df['volume'].rank(method='dense', ascending=False)
                                tier_month_df['etr_rank'] = tier_month_df['etr_ratio'].rank(method='dense', ascending=False)
                                tier_month_df['etd_rank'] = tier_month_df['etd_ratio'].rank(method='dense', ascending=False)

                                current_tier_month_data = tier_month_df[tier_month_df['country'] == country]
                                if not current_tier_month_data.empty:
                                    tier_monthly_rankings[tier][month_str] = {
                                        'partners_rank': int(current_tier_month_data.iloc[0]['partners_rank']),
                                        'earnings_rank': int(current_tier_month_data.iloc[0]['earnings_rank']),
                                        'revenue_rank': int(current_tier_month_data.iloc[0]['revenue_rank']),
                                        'deposits_rank': int(current_tier_month_data.iloc[0]['deposits_rank']),
                                        'active_clients_rank': int(current_tier_month_data.iloc[0]['active_clients_rank']),
                                        'new_clients_rank': int(current_tier_month_data.iloc[0]['new_clients_rank']),
                                        'volume_rank': int(current_tier_month_data.iloc[0]['volume_rank']),
                                        'etr_rank': int(current_tier_month_data.iloc[0]['etr_rank']),
                                        'etd_rank': int(current_tier_month_data.iloc[0]['etd_rank'])
                                    }

                except Exception as e:
                    logger.error(f"Error calculating tier monthly rankings for {month_str}: {str(e)}")

            # Calculate global totals for percentage calculations (matching Partner Overview methodology)
            global_summary = partner_data.groupby('partner_id').agg({
                'partner_tier': 'last',
                'total_earnings': 'sum',
                'total_deposits': 'sum',
                'active_clients': 'last',
                'new_active_clients': 'sum'
            }).reset_index()

            # UPDATED: Match Partner Overview - only use ACTIVE partners (exclude Inactive)
            active_global_summary = global_summary[global_summary['partner_tier'] != 'Inactive']

            global_totals = {
                'total_active_partners': len(active_global_summary),
                'total_company_revenue': float(active_global_summary['total_earnings'].sum()),  # Use total_earnings as revenue (matching Partner Overview)
                'total_partner_earnings': float(active_global_summary['total_earnings'].sum()),
                'total_deposits': float(active_global_summary['total_deposits'].sum()),
                'total_new_clients': int(active_global_summary['new_active_clients'].sum())
            }

            # Calculate global tier totals (matching Partner Overview methodology)
            tier_totals = {}
            for tier in ['Platinum', 'Gold', 'Silver', 'Bronze', 'Inactive']:
                tier_data = global_summary[global_summary['partner_tier'] == tier]
                if not tier_data.empty:
                    tier_totals[tier] = {
                        'total_active_partners': len(tier_data),
                        'total_company_revenue': float(tier_data['total_earnings'].sum()),  # Use total_earnings as revenue
                        'total_partner_earnings': float(tier_data['total_earnings'].sum()),
                        'total_deposits': float(tier_data['total_deposits'].sum()),
                        'total_new_clients': int(tier_data['new_active_clients'].sum())
                    }
                else:
                    tier_totals[tier] = {
                        'total_active_partners': 0,
                        'total_company_revenue': 0.0,
                        'total_partner_earnings': 0.0,
                        'total_deposits': 0.0,
                        'total_new_clients': 0
                    }

            global_totals['tier_totals'] = tier_totals

            # ENHANCEMENT: Add ranking information to monthly tier data
            for month_str in monthly_data.keys():
                # Add overall monthly rankings (non-tier-specific) to the monthly data
                if month_str in monthly_rankings:
                    for tier in monthly_data[month_str].keys():
                        if tier in monthly_data[month_str]:
                            monthly_data[month_str][tier].update({
                                'active_clients_rank': monthly_rankings[month_str].get('active_clients_rank', 0),
                                'earnings_rank': monthly_rankings[month_str].get('earnings_rank', 0),
                                'revenue_rank': monthly_rankings[month_str].get('revenue_rank', 0),
                                'deposits_rank': monthly_rankings[month_str].get('deposits_rank', 0),
                                'partners_rank': monthly_rankings[month_str].get('partners_rank', 0),
                                'new_clients_rank': monthly_rankings[month_str].get('new_clients_rank', 0),
                                'volume_rank': monthly_rankings[month_str].get('volume_rank', 0)
                            })

                # Add tier-specific monthly rankings to the monthly data
                for tier in monthly_data[month_str].keys():
                    if tier in tier_monthly_rankings and month_str in tier_monthly_rankings[tier]:
                        tier_ranks = tier_monthly_rankings[tier][month_str]
                        monthly_data[month_str][tier].update({
                            'tier_active_clients_rank': tier_ranks.get('active_clients_rank', 0),
                            'tier_earnings_rank': tier_ranks.get('earnings_rank', 0),
                            'tier_revenue_rank': tier_ranks.get('revenue_rank', 0),
                            'tier_deposits_rank': tier_ranks.get('deposits_rank', 0),
                            'tier_partners_rank': tier_ranks.get('partners_rank', 0),
                            'tier_new_clients_rank': tier_ranks.get('new_clients_rank', 0),
                            'tier_volume_rank': tier_ranks.get('volume_rank', 0)
                        })

            analytics_data = {
                'summary': summary,
                'monthly_tier_data': monthly_data,
                'tier_country_rankings': tier_country_rankings,
                'monthly_rankings': monthly_rankings,
                'tier_monthly_rankings': tier_monthly_rankings,  # NEW: Tier-specific monthly rankings
                'country_rankings': {},  # Not applicable for single country view
                'available_months': list(monthly_data.keys()) if monthly_data else [],  # Already sorted chronologically
                'global_totals': global_totals
            }

            return jsonify({
                'success': True,
                'data': analytics_data,
                'country': country
            })

        except Exception as e:
            logger.error(f"Error getting country tier analytics: {str(e)}")
            return jsonify({'error': str(e)}), 500
