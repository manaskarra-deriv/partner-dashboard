"""
Partner Management Tab Backend APIs

This module contains all the backend APIs for the Partner Management tab:
- Partner list with filtering and sorting
- Individual partner details
- Partner funnel data
"""

from flask import request, jsonify
import logging
import pandas as pd
from datetime import datetime
from utils import validate_partner_data
from db_integration import db

logger = logging.getLogger(__name__)

def register_partner_management_routes(app, get_partner_data):
    """Register all Partner Management tab routes"""

    @app.route('/api/partners', methods=['GET'])
    def get_partners():
        """Get filtered partner list"""
        try:
            partner_data = get_partner_data()
            if partner_data is None:
                return jsonify({'error': 'No data available'}), 400

            # Get query parameters
            partner_id = request.args.get('partner_id')
            country = request.args.get('country')
            region = request.args.get('region')
            tier = request.args.get('tier')
            is_app_dev = request.args.get('is_app_dev')

            # Numerical filter parameters
            active_clients_min = request.args.get('active_clients_min', type=int)
            active_clients_max = request.args.get('active_clients_max', type=int)
            new_clients_min = request.args.get('new_clients_min', type=int)
            new_clients_max = request.args.get('new_clients_max', type=int)
            etr_filter = request.args.get('etr_filter')
            etr_min = request.args.get('etr_min', type=float)
            etr_max = request.args.get('etr_max', type=float)

            limit = request.args.get('limit', 50, type=int)
            offset = request.args.get('offset', 0, type=int)
            sort_by = request.args.get('sort_by', 'total_earnings')
            sort_order = request.args.get('sort_order', 'desc')

            # Apply non-tier filters first
            filtered_data = partner_data.copy()

            if partner_id:
                # Filter by partner ID(s) - support comma-separated values
                partner_ids = [pid.strip() for pid in partner_id.split(',') if pid.strip()]
                if partner_ids:
                    filtered_data = filtered_data[filtered_data['partner_id'].astype(str).isin(partner_ids)]
            if country:
                filtered_data = filtered_data[filtered_data['country'] == country]
            if region:
                filtered_data = filtered_data[filtered_data['region'] == region]
            if is_app_dev:
                filtered_data = filtered_data[filtered_data['is_app_dev'] == (is_app_dev.lower() == 'true')]

            # Aggregate data by partner_id to show one row per partner (using latest values)
            partner_aggregated = filtered_data.groupby('partner_id').agg({
                # Static info - take latest occurrence (to match detail page)
                'first_name': 'last',
                'last_name': 'last',
                'username': 'last',
                'country': 'last',
                'region': 'last',
                'partner_tier': 'last',  # Use latest tier to match detail page
                'is_app_dev': 'last',
                'joined_date': 'last',
                # Financial metrics - sum across all months (cumulative) + recent month data for EtR
                'total_earnings': 'sum',
                'company_revenue': 'sum',
                'total_deposits': 'sum',  # Cumulative total deposits
                # Recent month metrics for consistent display (like active_clients)
                'volume_usd': 'last',  # Recent month volume (not cumulative)
                'active_clients': 'last',
                'new_active_clients': 'last',  # Recent month new clients (not cumulative)
            }).reset_index()

            # Calculate months count for each partner
            months_count = filtered_data.groupby('partner_id').size().reset_index(name='months_count')
            partner_aggregated = partner_aggregated.merge(months_count, on='partner_id')

            # Calculate consistent monthly average (total_earnings / months_count)
            partner_aggregated['avg_monthly_earnings'] = partner_aggregated['total_earnings'] / partner_aggregated['months_count']

            # Keep the original CSV field for reference but use consistent calculation for display
            partner_aggregated['avg_past_3_months_earnings'] = partner_aggregated['avg_monthly_earnings']

            # Calculate Lifetime EtR ratio for sorting (before filtering)
            def calculate_lifetime_etr_for_sorting(row):
                earnings = row['total_earnings']  # Use lifetime total earnings
                revenue = row['company_revenue']  # Use lifetime total company revenue
                if revenue == 0:
                    return 0
                ratio = (earnings / revenue) * 100
                # For sorting purposes, treat loss scenarios as negative values
                if revenue < 0 or earnings > revenue:
                    return -abs(ratio)  # Make it negative for proper sorting
                return ratio

            partner_aggregated['etr_ratio'] = partner_aggregated.apply(calculate_lifetime_etr_for_sorting, axis=1)

            # Convert aggregated values to proper types
            for col in ['total_earnings', 'company_revenue', 'total_deposits', 'volume_usd', 'active_clients', 'new_active_clients', 'avg_monthly_earnings', 'avg_past_3_months_earnings', 'etr_ratio']:
                if col in partner_aggregated.columns:
                    if col in ['active_clients', 'new_active_clients']:
                        partner_aggregated[col] = partner_aggregated[col].astype(int)
                    else:
                        partner_aggregated[col] = partner_aggregated[col].astype(float)

            # Apply tier filter AFTER aggregation (filter by current/latest tier)
            if tier:
                partner_aggregated = partner_aggregated[partner_aggregated['partner_tier'] == tier]

            # Apply numerical filters AFTER aggregation
            if active_clients_min is not None:
                partner_aggregated = partner_aggregated[partner_aggregated['active_clients'] >= active_clients_min]
            if active_clients_max is not None:
                partner_aggregated = partner_aggregated[partner_aggregated['active_clients'] <= active_clients_max]
            if new_clients_min is not None:
                partner_aggregated = partner_aggregated[partner_aggregated['new_active_clients'] >= new_clients_min]
            if new_clients_max is not None:
                partner_aggregated = partner_aggregated[partner_aggregated['new_active_clients'] <= new_clients_max]

            # Apply EtR filter (using existing etr_ratio column based on lifetime data)
            if etr_filter:
                if etr_filter == 'double-loss':
                    # Filter for double negative: lifetime revenue is negative (company lost money)
                    partner_aggregated = partner_aggregated[partner_aggregated['company_revenue'] < 0]
                elif etr_filter == 'unprofitable':
                    # Filter for single negative: lifetime earnings > positive lifetime revenue (unprofitable partner)
                    unprofitable_condition = (
                        (partner_aggregated['company_revenue'] > 0) &
                        (partner_aggregated['total_earnings'] > partner_aggregated['company_revenue'])
                    )
                    partner_aggregated = partner_aggregated[unprofitable_condition]
                elif etr_filter == 'critically-low':
                    partner_aggregated = partner_aggregated[
                        (partner_aggregated['etr_ratio'] >= 0.1) & (partner_aggregated['etr_ratio'] < 10)
                    ]
                elif etr_filter == 'very-low':
                    partner_aggregated = partner_aggregated[
                        (partner_aggregated['etr_ratio'] >= 10) & (partner_aggregated['etr_ratio'] < 20)
                    ]
                elif etr_filter == 'low':
                    partner_aggregated = partner_aggregated[
                        (partner_aggregated['etr_ratio'] >= 20) & (partner_aggregated['etr_ratio'] < 30)
                    ]
                elif etr_filter == 'fair':
                    partner_aggregated = partner_aggregated[
                        (partner_aggregated['etr_ratio'] >= 30) & (partner_aggregated['etr_ratio'] <= 40)
                    ]
                elif etr_filter == 'high':
                    partner_aggregated = partner_aggregated[partner_aggregated['etr_ratio'] > 40]
                elif etr_filter == 'custom':
                    if etr_min is not None:
                        partner_aggregated = partner_aggregated[partner_aggregated['etr_ratio'] >= etr_min]
                    if etr_max is not None:
                        partner_aggregated = partner_aggregated[partner_aggregated['etr_ratio'] <= etr_max]

            # Sort aggregated data
            if sort_by in partner_aggregated.columns:
                ascending = sort_order.lower() == 'asc'
                partner_aggregated = partner_aggregated.sort_values(by=sort_by, ascending=ascending)

            # Apply pagination
            total_count = len(partner_aggregated)
            paginated_data = partner_aggregated.iloc[offset:offset + limit]

            # Remove etr_ratio column before sending to frontend (frontend calculates it for display)
            if 'etr_ratio' in paginated_data.columns:
                paginated_data = paginated_data.drop('etr_ratio', axis=1)

            # Convert to JSON-serializable format
            result = {
                'partners': paginated_data.to_dict('records'),
                'total_count': total_count,
                'has_more': offset + limit < total_count
            }

            return jsonify(result)

        except Exception as e:
            logger.error(f"Error getting partners: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/partners/<partner_id>', methods=['GET'])
    def get_partner_detail(partner_id):
        """Get detailed information for a specific partner"""
        try:
            partner_data = get_partner_data()
            if partner_data is None:
                return jsonify({'error': 'No data available'}), 400

            partner_records = partner_data[partner_data['partner_id'] == partner_id]

            if partner_records.empty:
                return jsonify({'error': 'Partner not found'}), 404

            # Get partner basic info (using latest record for static fields)
            latest_record = partner_records.iloc[-1]

            # Calculate aggregated totals across all months (convert to Python types)
            ytd_totals = {
                'total_earnings': float(partner_records['total_earnings'].sum()),
                'company_revenue': float(partner_records['company_revenue'].sum()),
                'total_deposits': float(partner_records['total_deposits'].sum()),
                'volume_usd': float(partner_records['volume_usd'].sum()),
                'total_active_clients': int(partner_records['active_clients'].iloc[-1]),  # Latest month's active clients
                'total_new_clients': int(partner_records['new_active_clients'].sum()),    # Sum of all new clients acquired
                'avg_monthly_earnings': float(partner_records['total_earnings'].mean()),
                'avg_monthly_revenue': float(partner_records['company_revenue'].mean()),
                'avg_monthly_deposits': float(partner_records['total_deposits'].mean()),
                'avg_monthly_volume': float(partner_records['volume_usd'].mean()),
                'avg_monthly_active_clients': float(partner_records['active_clients'].mean()),
                'avg_monthly_new_clients': float(partner_records['new_active_clients'].mean()),
                'months_count': int(len(partner_records))
            }

            # Get current month (latest) performance (convert to Python types)
            current_month = {
                'month': latest_record['month'].isoformat() if pd.notna(latest_record['month']) else None,
                'total_earnings': float(latest_record['total_earnings']),
                'company_revenue': float(latest_record['company_revenue']),
                'total_deposits': float(latest_record['total_deposits']),
                'volume_usd': float(latest_record['volume_usd']),
                'active_clients': int(latest_record['active_clients']),
                'new_active_clients': int(latest_record['new_active_clients'])
            }

            # Calculate monthly performance
            monthly_performance = partner_records.groupby('month').agg({
                'partner_tier': 'first',
                'total_earnings': 'first',
                'active_clients': 'first',
                'new_active_clients': 'first',
                'company_revenue': 'first',
                'total_deposits': 'first',
                'volume_usd': 'first'
            }).reset_index().sort_values('month', ascending=False).to_dict('records')

            # Combine basic info with totals
            partner_info = latest_record.to_dict()
            partner_info.update(ytd_totals)

            # Get additional partner information from database (including date_joined for age calculation)
            try:
                partner_db_info = db.get_partner_info_details(partner_id)
                if partner_db_info:
                    # Calculate partner age if date_joined is available
                    if partner_db_info.get('date_joined'):
                        from datetime import datetime

                        # Parse the date_joined string back to datetime for calculation
                        date_joined = datetime.fromisoformat(partner_db_info['date_joined'].replace('Z', '+00:00'))
                        current_date = datetime.now(date_joined.tzinfo) if date_joined.tzinfo else datetime.now()

                        # Calculate age in days
                        age_days = (current_date - date_joined).days

                        # Calculate age components
                        years = age_days // 365
                        remaining_days = age_days % 365
                        months = remaining_days // 30
                        days = remaining_days % 30

                        # Create age badge based on tenure
                        if age_days >= 1825:  # 5+ years
                            age_badge = 'age-5yr-plus'
                            age_milestone = '5+ Years'
                        elif age_days >= 1460:  # 4+ years
                            age_badge = 'age-4yr'
                            age_milestone = '4+ Years'
                        elif age_days >= 1095:  # 3+ years
                            age_badge = 'age-3yr'
                            age_milestone = '3+ Years'
                        elif age_days >= 730:   # 2+ years
                            age_badge = 'age-2yr'
                            age_milestone = '2+ Years'
                        elif age_days >= 548:   # 18+ months
                            age_badge = 'age-18mo'
                            age_milestone = '18+ Months'
                        elif age_days >= 365:   # 1+ year
                            age_badge = 'age-1yr'
                            age_milestone = '1+ Year'
                        elif age_days >= 180:   # 6+ months
                            age_badge = 'age-6mo'
                            age_milestone = '6+ Months'
                        elif age_days >= 90:    # 3+ months
                            age_badge = 'age-3mo'
                            age_milestone = '3+ Months'
                        elif age_days >= 30:    # 1+ month
                            age_badge = 'age-1mo'
                            age_milestone = '1+ Month'
                        else:
                            age_badge = 'new'
                            age_milestone = 'New Partner'

                        # Create readable age string
                        if years > 0:
                            if months > 0:
                                age_display = f"{years} year{'s' if years != 1 else ''}, {months} month{'s' if months != 1 else ''}"
                            else:
                                age_display = f"{years} year{'s' if years != 1 else ''}"
                        elif months > 0:
                            if days > 0:
                                age_display = f"{months} month{'s' if months != 1 else ''}, {days} day{'s' if days != 1 else ''}"
                            else:
                                age_display = f"{months} month{'s' if months != 1 else ''}"
                        else:
                            age_display = f"{age_days} day{'s' if age_days != 1 else ''}"

                        # Add age information to partner_info
                        partner_info.update({
                            'date_joined': partner_db_info['date_joined'],
                            'partner_age_days': age_days,
                            'partner_age_display': age_display,
                            'partner_age_badge': age_badge,
                            'partner_age_milestone': age_milestone
                        })

                    # Add other useful fields from partner_info table
                    useful_fields = [
                        'partner_status', 'partner_level', 'aff_type', 'activation_phase',
                        'is_master_plan', 'is_revshare_plan', 'is_turnover_plan', 'is_cpa_plan', 'is_ib_plan',
                        'parent_partner_id', 'subaff_count', 'first_client_joined_date', 'first_client_deposit_date',
                        'first_client_trade_date', 'first_earning_date', 'last_client_joined_date', 'last_earning_date',
                        'webinar_count', 'seminar_count', 'sponsorship_event_count', 'conference_count', 'attended_onboarding_event'
                    ]

                    for field in useful_fields:
                        if field in partner_db_info and partner_db_info[field] is not None:
                            partner_info[field] = partner_db_info[field]

            except Exception as e:
                logger.warning(f"Could not fetch additional partner info for {partner_id}: {str(e)}")
                # Continue without the additional info

            partner_detail = {
                'partner_info': partner_info,
                'current_month': current_month,
                'monthly_performance': monthly_performance,
                'total_records': len(partner_records)
            }

            return jsonify(partner_detail)

        except Exception as e:
            logger.error(f"Error getting partner detail: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/partners/<partner_id>/funnel', methods=['GET'])
    def get_partner_funnel(partner_id):
        """Get monthly funnel performance data for a specific partner"""
        try:
            # Get funnel data from Supabase
            funnel_data = db.get_partner_funnel_data(partner_id)

            if not funnel_data:
                return jsonify({
                    'funnel_data': [],
                    'summary': {
                        'total_months': 0,
                        'total_demo': 0,
                        'total_real': 0,
                        'total_deposits': 0,
                        'total_trades': 0,
                        'avg_deposit_rate': 0.0,
                        'avg_trade_rate': 0.0
                    }
                })

            # Calculate summary metrics based on new funnel structure
            total_demo = sum(month['demo_count'] for month in funnel_data)
            total_real = sum(month['real_count'] for month in funnel_data)
            total_deposits = sum(month['deposit_count'] for month in funnel_data)
            total_trades = sum(month['traded_count'] for month in funnel_data)

            avg_deposit_rate = (total_deposits / total_demo * 100) if total_demo > 0 else 0
            avg_trade_rate = (total_trades / total_demo * 100) if total_demo > 0 else 0

            # Get acquisition summary
            try:
                acquisition_data = db.get_partner_acquisition_summary(partner_id)
            except Exception as e:
                logger.warning(f"Could not fetch acquisition data for partner {partner_id}: {str(e)}")
                acquisition_data = {'acquisition_channels': [], 'total_channels': 0}

            return jsonify({
                'funnel_data': funnel_data,
                'summary': {
                    'total_months': len(funnel_data),
                    'total_demo': total_demo,
                    'total_real': total_real,
                    'total_deposits': total_deposits,
                    'total_trades': total_trades,
                    'avg_deposit_rate': round(avg_deposit_rate, 2),
                    'avg_trade_rate': round(avg_trade_rate, 2),
                    'recent_month': funnel_data[0] if funnel_data else None
                },
                'acquisition_data': acquisition_data
            })

        except Exception as e:
            logger.error(f"Error getting funnel data for partner {partner_id}: {str(e)}")
            return jsonify({'error': str(e)}), 500