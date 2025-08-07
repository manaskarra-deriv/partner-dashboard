import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
import logging
from dotenv import load_dotenv
from typing import List, Dict, Any
from datetime import datetime
import time
import threading

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SupabaseDB:
    def __init__(self):
        self.db_params = {
            'host': os.getenv('host'),
            'port': os.getenv('port'),
            'database': os.getenv('dbname'),
            'user': os.getenv('user'),
            'password': os.getenv('password')
        }
        self.connection_pool = None
        self.lock = threading.Lock()
        self._initialize_pool()

    def _initialize_pool(self):
        """Initialize connection pool with retry logic"""
        max_retries = 3
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                # Close existing pool if it exists
                if self.connection_pool:
                    try:
                        self.connection_pool.closeall()
                    except Exception:
                        pass
                    self.connection_pool = None

                self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=1,  # Reduced minimum connections
                    maxconn=8,   # Reduced maximum connections for better stability
                    **self.db_params,
                    # Enhanced connection parameters
                    connect_timeout=30,
                    keepalives=1,
                    keepalives_idle=600,  # 10 minutes (longer than 5 min timeout)
                    keepalives_interval=30,
                    keepalives_count=3,
                    application_name='PDash_Backend',
                    # Add statement timeout to prevent hanging queries
                    options='-c statement_timeout=60000'  # 60 seconds
                )
                logger.info("Successfully initialized connection pool to Supabase database")
                return
            except Exception as e:
                logger.error(f"Failed to initialize connection pool (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise e

    def get_connection(self):
        """Get a connection from the pool with automatic retry"""
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                with self.lock:
                    if self.connection_pool is None:
                        logger.warning("Connection pool is None, reinitializing...")
                        self._initialize_pool()

                    conn = self.connection_pool.getconn()

                    # Test the connection
                    if conn.closed != 0:
                        logger.warning("Retrieved closed connection, getting new one...")
                        self.connection_pool.putconn(conn, close=True)
                        conn = self.connection_pool.getconn()

                    # Test with a simple query
                    with conn.cursor() as test_cursor:
                        test_cursor.execute("SELECT 1")
                        test_cursor.fetchone()

                    return conn

            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    # Try to reinitialize pool if connection fails
                    try:
                        with self.lock:
                            if self.connection_pool:
                                self.connection_pool.closeall()
                            self._initialize_pool()
                    except Exception:
                        pass
                    time.sleep(retry_delay)
                else:
                    raise e

    def return_connection(self, conn, close=False):
        """Return a connection to the pool"""
        if not conn:
            return

        try:
            with self.lock:
                if self.connection_pool and conn:
                    # Check if connection is still valid before returning
                    if conn.closed == 0 and not close:
                        self.connection_pool.putconn(conn, close=False)
                    else:
                        # Close invalid connections
                        try:
                            conn.close()
                        except Exception:
                            pass
                        self.connection_pool.putconn(conn, close=True)
        except Exception as e:
            # If we can't return to pool, just close the connection
            try:
                if conn and conn.closed == 0:
                    conn.close()
            except Exception:
                pass
            logger.warning(f"Could not return connection to pool (closed it instead): {str(e)}")

    def execute_query(self, query, params=None, fetch_all=True):
        """Execute a query with automatic connection management and retry logic"""
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            conn = None
            try:
                conn = self.get_connection()

                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Set a statement timeout for this specific query
                    cursor.execute("SET statement_timeout = '60s'")
                    cursor.execute(query, params)

                    if fetch_all:
                        results = cursor.fetchall()
                        # Convert to list of dictionaries for JSON serialization
                        return [dict(row) for row in results]
                    else:
                        result = cursor.fetchone()
                        return dict(result) if result else None

            except Exception as e:
                error_msg = str(e).lower()

                # Enhanced error detection for various timeout and connection issues
                is_connection_error = any(keyword in error_msg for keyword in [
                    'connection', 'timeout', 'broken', 'closed', 'lost',
                    'network', 'server closed', 'ssl', 'canceling statement',
                    'statement timeout', 'query cancelled', 'connection lost'
                ])

                if is_connection_error and attempt < max_retries - 1:
                    logger.warning(f"Connection/timeout error on attempt {attempt + 1}: {str(e)}")
                    if conn:
                        self.return_connection(conn, close=True)
                        conn = None

                    # Exponential backoff with jitter
                    delay = retry_delay * (attempt + 1) + (attempt * 0.5)
                    time.sleep(delay)
                    continue

                # For non-connection errors or final attempt
                if attempt == max_retries - 1:
                    logger.error(f"Query execution failed after {max_retries} attempts: {str(e)}")
                else:
                    logger.error(f"Query execution failed (non-retryable): {str(e)}")

                # Return connection before raising error
                if conn:
                    self.return_connection(conn, close=is_connection_error)
                    conn = None

                raise e

            finally:
                # Ensure connection is always returned
                if conn:
                    self.return_connection(conn)

    def disconnect(self):
        """Close all connections in the pool"""
        try:
            with self.lock:
                if self.connection_pool:
                    self.connection_pool.closeall()
                    self.connection_pool = None
                logger.info("All database connections closed")
        except Exception as e:
            logger.error(f"Error closing connection pool: {str(e)}")

    def get_partner_funnel_data(self, partner_id: str) -> List[Dict[str, Any]]:
        """
        Get monthly funnel performance data for a specific partner with Demo, Real, Deposit, Traded stages.

        Args:
            partner_id (str): The partner ID to get funnel data for

        Returns:
            List[Dict]: Monthly funnel data with demo, real, deposit, traded counts and conversion rates
        """
        try:
            table_name = "client.user_profile"

            query = f"""
            SELECT
                DATE_TRUNC('month', real_joined_date)::date as joined_month,
                COUNT(DISTINCT binary_user_id) as demo_count,
                COUNT(DISTINCT binary_user_id) as real_count,
                COUNT(DISTINCT CASE WHEN first_deposit_date IS NOT NULL THEN binary_user_id END) as deposit_count,
                COUNT(DISTINCT CASE WHEN first_trade_date IS NOT NULL THEN binary_user_id END) as traded_count,
                100.0 as demo_to_real_rate,
                ROUND(
                    (COUNT(DISTINCT CASE WHEN first_deposit_date IS NOT NULL THEN binary_user_id END)::numeric /
                     NULLIF(COUNT(DISTINCT binary_user_id), 0)) * 100, 2
                ) as demo_to_deposit_rate,
                ROUND(
                    (COUNT(DISTINCT CASE WHEN first_trade_date IS NOT NULL THEN binary_user_id END)::numeric /
                     NULLIF(COUNT(DISTINCT binary_user_id), 0)) * 100, 2
                ) as demo_to_trade_rate,
                ROUND(
                    AVG(CASE WHEN first_deposit_amount_usd IS NOT NULL THEN first_deposit_amount_usd::numeric ELSE 0 END), 2
                ) as avg_first_deposit_amount
            FROM {table_name}
            WHERE affiliated_partner_id = %s
                AND real_joined_date IS NOT NULL
                AND is_internal = FALSE
            GROUP BY DATE_TRUNC('month', real_joined_date)::date
            ORDER BY joined_month DESC
            LIMIT 12
            """

            results = self.execute_query(query, (partner_id,))

            # Format data for frontend
            funnel_data = []
            for row in results:
                # Convert date to string for JSON serialization
                if row['joined_month']:
                    row['joined_month'] = row['joined_month'].strftime('%b %Y')  # Format as "Jan 2025"

                # Ensure numeric values are properly formatted
                for key in ['demo_count', 'real_count', 'deposit_count', 'traded_count']:
                    row[key] = int(row[key]) if row[key] is not None else 0

                for key in ['demo_to_real_rate', 'demo_to_deposit_rate', 'demo_to_trade_rate', 'avg_first_deposit_amount']:
                    row[key] = float(row[key]) if row[key] is not None else 0.0

                funnel_data.append(row)

            logger.info(f"Retrieved funnel data for partner {partner_id}: {len(funnel_data)} months")
            return funnel_data

        except Exception as e:
            logger.error(f"Error fetching funnel data for partner {partner_id}: {str(e)}")
            # Return empty list instead of raising to prevent frontend hanging
            return []

    def get_partner_acquisition_summary(self, partner_id: str) -> Dict[str, Any]:
        """
        Get acquisition channel summary for a partner.

        Args:
            partner_id (str): The partner ID to get summary for

        Returns:
            Dict: Summary of acquisition channels and client sources
        """
        try:
            query = """
            SELECT
                acquisition_channel,
                utm_source,
                utm_medium,
                COUNT(DISTINCT binary_user_id) as client_count,
                COUNT(DISTINCT CASE WHEN first_deposit_date IS NOT NULL THEN binary_user_id END) as depositing_clients,
                ROUND(AVG(CASE WHEN first_deposit_amount_usd IS NOT NULL THEN first_deposit_amount_usd::numeric ELSE 0 END), 2) as avg_deposit_amount
            FROM client.user_profile
            WHERE affiliated_partner_id = %s
                AND real_joined_date IS NOT NULL
                AND is_internal = FALSE
            GROUP BY acquisition_channel, utm_source, utm_medium
            ORDER BY client_count DESC
            LIMIT 10
            """

            results = self.execute_query(query, (partner_id,))

            logger.info(f"Retrieved acquisition summary for partner {partner_id}: {len(results)} channels")
            return {
                'acquisition_channels': results,
                'total_channels': len(results)
            }

        except Exception as e:
            logger.error(f"Error fetching acquisition summary for partner {partner_id}: {str(e)}")
            return {'acquisition_channels': [], 'total_channels': 0}

    def get_partner_regions_mapping(self) -> Dict[str, str]:
        """
        Get mapping of partner IDs to their GP regions from partner_info table.
        This overrides the region from CSV data with more accurate GP regions.

        Returns:
            Dict[str, str]: Mapping of partner_id to region
        """
        try:
            query = """
            SELECT
                partner_id,
                partner_region
            FROM partner.partner_info
            WHERE partner_region IS NOT NULL
                AND partner_region != ''
            """

            results = self.execute_query(query)

            # Convert to dictionary mapping
            region_mapping = {}
            for row in results:
                partner_id = str(row['partner_id']) if row['partner_id'] else None
                region = row['partner_region']
                if partner_id and region:
                    region_mapping[partner_id] = region

            logger.info(f"Retrieved GP region mapping for {len(region_mapping)} partners")
            return region_mapping

        except Exception as e:
            logger.error(f"Error fetching GP regions mapping: {str(e)}")
            return {}

    def get_partner_info_details(self, partner_id: str) -> Dict[str, Any]:
        """
        Get detailed partner information including join date for age calculation.

        Args:
            partner_id (str): The partner ID to get info for

        Returns:
            Dict: Partner information including date_joined, status, level, etc.
        """
        try:
            query = """
            SELECT
                partner_id,
                date_joined,
                partner_status,
                partner_level,
                partner_region,
                partner_country,
                aff_type,
                activation_phase,
                is_app_dev,
                is_pa,
                is_master_plan,
                is_revshare_plan,
                is_turnover_plan,
                is_cpa_plan,
                is_ib_plan,
                parent_partner_id,
                subaff_count,
                first_client_joined_date,
                first_client_deposit_date,
                first_client_trade_date,
                first_earning_date,
                last_client_joined_date,
                last_earning_date,
                webinar_count,
                seminar_count,
                sponsorship_event_count,
                conference_count,
                attended_onboarding_event
            FROM partner.partner_info
            WHERE partner_id = %s
            """

            results = self.execute_query(query, (partner_id,))

            if results:
                partner_info = results[0]

                # Convert dates to strings for JSON serialization
                date_fields = [
                    'date_joined', 'first_client_joined_date', 'first_client_deposit_date',
                    'first_client_trade_date', 'first_earning_date', 'last_client_joined_date',
                    'last_earning_date'
                ]

                for field in date_fields:
                    if partner_info.get(field):
                        partner_info[field] = partner_info[field].isoformat()

                # Ensure boolean fields are properly formatted
                boolean_fields = [
                    'is_app_dev', 'is_pa', 'is_master_plan', 'is_revshare_plan',
                    'is_turnover_plan', 'is_cpa_plan', 'is_ib_plan', 'attended_onboarding_event'
                ]

                for field in boolean_fields:
                    if field in partner_info:
                        partner_info[field] = bool(partner_info[field])

                # Ensure numeric fields are properly formatted
                numeric_fields = ['partner_level', 'subaff_count', 'webinar_count', 'seminar_count', 'sponsorship_event_count', 'conference_count']
                for field in numeric_fields:
                    if partner_info.get(field) is not None:
                        partner_info[field] = int(partner_info[field])

                logger.info(f"Retrieved detailed info for partner {partner_id}")
                return partner_info
            else:
                logger.warning(f"No partner info found for partner {partner_id}")
                return {}

        except Exception as e:
            logger.error(f"Error fetching partner info for {partner_id}: {str(e)}")
            return {}

    def get_partner_application_funnel_data(self, selected_month: str = None, selected_countries: list = None) -> Dict[str, Any]:
        """
        Get partner application funnel data including monthly trends, activation metrics,
        and distribution by country/region.

        Args:
            selected_month (str, optional): Filter by specific month (e.g., 'Jul 2025')
            selected_countries (list, optional): Filter by specific countries (e.g., ['Kenya', 'Nigeria'])

        Returns:
            Dict: Comprehensive partner application funnel analytics
        """
        try:
            # Monthly applications trend (always show all months)
            monthly_query = """
            SELECT
                DATE_TRUNC('month', date_joined)::date as application_month,
                COUNT(DISTINCT partner_id) as total_applications,
                COUNT(DISTINCT CASE WHEN first_client_joined_date IS NOT NULL THEN partner_id END) as client_activated,
                COUNT(DISTINCT CASE WHEN first_earning_date IS NOT NULL THEN partner_id END) as earning_activated,
                COUNT(DISTINCT CASE WHEN parent_partner_id IS NOT NULL THEN partner_id END) as sub_partners,
                COUNT(DISTINCT CASE WHEN parent_partner_id IS NULL THEN partner_id END) as direct_partners,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (
                    CASE WHEN first_client_joined_date IS NOT NULL
                    THEN (first_client_joined_date - date_joined)
                    END
                ))::NUMERIC, 1) as avg_days_to_first_client,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (
                    CASE WHEN first_earning_date IS NOT NULL
                    THEN (first_earning_date - date_joined)
                    END
                ))::NUMERIC, 1) as avg_days_to_first_earning
            FROM partner.partner_info
            WHERE date_joined IS NOT NULL
                AND is_internal = FALSE
                AND date_joined >= CURRENT_DATE - INTERVAL '12 months'
            GROUP BY DATE_TRUNC('month', date_joined)::date
            ORDER BY application_month DESC
            LIMIT 12
            """

            monthly_results = self.execute_query(monthly_query)

            # Prepare filter conditions
            month_filter_condition = ""
            if selected_month and selected_month != 'all':
                # Convert 'Jul 2025' format to date range
                try:
                    from datetime import datetime
                    parsed_date = datetime.strptime(selected_month, '%b %Y')
                    month_filter_condition = f"AND DATE_TRUNC('month', date_joined) = DATE_TRUNC('month', DATE '{parsed_date.strftime('%Y-%m-01')}')"
                except ValueError:
                    logger.warning(f"Invalid month format: {selected_month}")
                    month_filter_condition = ""

            # Prepare country filter condition for multiple countries
            country_filter_condition = ""
            if selected_countries and len(selected_countries) > 0:
                # Escape single quotes and create IN clause
                escaped_countries = [country.replace("'", "''") for country in selected_countries]
                countries_str = "', '".join(escaped_countries)
                country_filter_condition = f"AND partner_country IN ('{countries_str}')"

            # Country distribution (with optional month and country filters)
            country_query = f"""
            SELECT
                partner_country,
                COUNT(DISTINCT partner_id) as total_applications,
                COUNT(DISTINCT CASE WHEN first_client_joined_date IS NOT NULL THEN partner_id END) as client_activated,
                COUNT(DISTINCT CASE WHEN first_earning_date IS NOT NULL THEN partner_id END) as earning_activated,
                COUNT(DISTINCT CASE WHEN parent_partner_id IS NOT NULL THEN partner_id END) as sub_partners,
                ROUND(
                    (COUNT(DISTINCT CASE WHEN first_client_joined_date IS NOT NULL THEN partner_id END)::numeric /
                     NULLIF(COUNT(DISTINCT partner_id), 0)) * 100, 1
                ) as client_activation_rate,
                ROUND(
                    (COUNT(DISTINCT CASE WHEN first_earning_date IS NOT NULL THEN partner_id END)::numeric /
                     NULLIF(COUNT(DISTINCT partner_id), 0)) * 100, 1
                ) as earning_activation_rate,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (
                    CASE WHEN first_client_joined_date IS NOT NULL
                    THEN (first_client_joined_date - date_joined)
                    END
                ))::NUMERIC, 1) as avg_days_to_first_client,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (
                    CASE WHEN first_earning_date IS NOT NULL
                    THEN (first_earning_date - date_joined)
                    END
                ))::NUMERIC, 1) as avg_days_to_first_earning
            FROM partner.partner_info
            WHERE date_joined IS NOT NULL
                AND is_internal = FALSE
                AND date_joined >= CURRENT_DATE - INTERVAL '12 months'
                AND partner_country IS NOT NULL
                {month_filter_condition}
                {country_filter_condition}
            GROUP BY partner_country
            ORDER BY total_applications DESC
            LIMIT 15
            """

            country_results = self.execute_query(country_query)

            # GP Region distribution (with optional month filter)
            region_query = f"""
            SELECT
                partner_region,
                COUNT(DISTINCT partner_id) as total_applications,
                COUNT(DISTINCT CASE WHEN first_client_joined_date IS NOT NULL THEN partner_id END) as client_activated,
                COUNT(DISTINCT CASE WHEN first_earning_date IS NOT NULL THEN partner_id END) as earning_activated,
                COUNT(DISTINCT CASE WHEN parent_partner_id IS NOT NULL THEN partner_id END) as sub_partners,
                ROUND(
                    (COUNT(DISTINCT CASE WHEN first_client_joined_date IS NOT NULL THEN partner_id END)::numeric /
                     NULLIF(COUNT(DISTINCT partner_id), 0)) * 100, 1
                ) as client_activation_rate,
                ROUND(
                    (COUNT(DISTINCT CASE WHEN first_earning_date IS NOT NULL THEN partner_id END)::numeric /
                     NULLIF(COUNT(DISTINCT partner_id), 0)) * 100, 1
                ) as earning_activation_rate,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (
                    CASE WHEN first_client_joined_date IS NOT NULL
                    THEN (first_client_joined_date - date_joined)
                    END
                ))::NUMERIC, 1) as avg_days_to_first_client,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (
                    CASE WHEN first_earning_date IS NOT NULL
                    THEN (first_earning_date - date_joined)
                    END
                ))::NUMERIC, 1) as avg_days_to_first_earning
            FROM partner.partner_info
            WHERE date_joined IS NOT NULL
                AND is_internal = FALSE
                AND date_joined >= CURRENT_DATE - INTERVAL '12 months'
                AND partner_region IS NOT NULL
                {month_filter_condition}
            GROUP BY partner_region
            ORDER BY total_applications DESC
            """

            region_results = self.execute_query(region_query)

            # Overall summary metrics (with optional month and country filters)
            summary_query = f"""
            SELECT
                COUNT(DISTINCT partner_id) as total_applications,
                COUNT(DISTINCT CASE WHEN first_client_joined_date IS NOT NULL THEN partner_id END) as client_activated,
                COUNT(DISTINCT CASE WHEN first_earning_date IS NOT NULL THEN partner_id END) as earning_activated,
                COUNT(DISTINCT CASE WHEN parent_partner_id IS NOT NULL THEN partner_id END) as sub_partners,
                COUNT(DISTINCT CASE WHEN parent_partner_id IS NULL THEN partner_id END) as direct_partners,
                COUNT(CASE WHEN is_app_dev = true THEN 1 END) as api_developers,
                ROUND(
                    (COUNT(DISTINCT CASE WHEN first_client_joined_date IS NOT NULL THEN partner_id END)::numeric /
                     NULLIF(COUNT(DISTINCT partner_id), 0)) * 100, 1
                ) as client_activation_rate,
                ROUND(
                    (COUNT(DISTINCT CASE WHEN first_earning_date IS NOT NULL THEN partner_id END)::numeric /
                     NULLIF(COUNT(DISTINCT partner_id), 0)) * 100, 1
                ) as earning_activation_rate,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (
                    CASE WHEN first_client_joined_date IS NOT NULL
                    THEN (first_client_joined_date - date_joined)
                    END
                ))::NUMERIC, 1) as avg_days_to_first_client,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (
                    CASE WHEN first_earning_date IS NOT NULL
                    THEN (first_earning_date - date_joined)
                    END
                ))::NUMERIC, 1) as avg_days_to_first_earning
            FROM partner.partner_info
            WHERE date_joined IS NOT NULL
                AND is_internal = FALSE
                AND date_joined >= CURRENT_DATE - INTERVAL '12 months'
                {month_filter_condition}
                {country_filter_condition}
            """

            summary_results = self.execute_query(summary_query)

            # Format monthly data for frontend
            monthly_data = []
            for row in monthly_results:
                if row['application_month']:
                    row['application_month'] = row['application_month'].strftime('%b %Y')

                # Ensure numeric values are properly formatted
                for key in ['total_applications', 'client_activated', 'earning_activated', 'sub_partners', 'direct_partners']:
                    row[key] = int(row[key]) if row[key] is not None else 0

                for key in ['avg_days_to_first_client', 'avg_days_to_first_earning']:
                    row[key] = float(row[key]) if row[key] is not None else 0.0

                # Calculate conversion rates
                total = row['total_applications']
                if total > 0:
                    row['client_activation_rate'] = round((row['client_activated'] / total) * 100, 1)
                    row['earning_activation_rate'] = round((row['earning_activated'] / total) * 100, 1)
                else:
                    row['client_activation_rate'] = 0.0
                    row['earning_activation_rate'] = 0.0

                monthly_data.append(row)

            # Format country and region data
            for dataset in [country_results, region_results]:
                for row in dataset:
                    for key in ['total_applications', 'client_activated', 'earning_activated', 'sub_partners']:
                        row[key] = int(row[key]) if row[key] is not None else 0
                    for key in ['client_activation_rate', 'earning_activation_rate']:
                        row[key] = float(row[key]) if row[key] is not None else 0.0

            # Format summary data
            summary = summary_results[0] if summary_results and len(summary_results) > 0 else {}
            for key in ['total_applications', 'client_activated', 'earning_activated', 'sub_partners', 'direct_partners', 'api_developers']:
                summary[key] = int(summary[key]) if summary.get(key) is not None else 0
            for key in ['client_activation_rate', 'earning_activation_rate', 'avg_days_to_first_client', 'avg_days_to_first_earning']:
                summary[key] = float(summary[key]) if summary.get(key) is not None else 0.0

            logger.info(f"Retrieved partner application funnel data: {len(monthly_data)} months, {len(country_results)} countries, {len(region_results)} regions")

            return {
                'monthly_data': monthly_data,
                'country_distribution': country_results,
                'region_distribution': region_results,
                'summary': summary
            }

        except Exception as e:
            logger.error(f"Error fetching partner application funnel data: {str(e)}")
            return {
                'monthly_data': [],
                'country_distribution': [],
                'region_distribution': [],
                'summary': {}
            }

    def get_partner_application_countries(self) -> List[str]:
        """
        Get list of all countries that have partner applications in the last 12 months

        Returns:
            List[str]: List of country names sorted alphabetically
        """
        try:
            query = """
            SELECT partner_country, COUNT(*) as application_count
            FROM partner.partner_info
            WHERE date_joined IS NOT NULL
                AND date_joined >= CURRENT_DATE - INTERVAL '12 months'
                AND partner_country IS NOT NULL
            GROUP BY partner_country
            ORDER BY partner_country ASC
            """

            results = self.execute_query(query)
            countries = [row['partner_country'] for row in results if row['partner_country']]

            logger.info(f"Retrieved {len(countries)} countries for application funnel filter (sorted alphabetically)")
            return countries

        except Exception as e:
            logger.error(f"Error getting partner application countries: {str(e)}")
            return []

    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the database connection

        Returns:
            Dict: Health status information
        """
        try:
            start_time = time.time()
            result = self.execute_query("SELECT 1 as health_check, NOW() as server_time", fetch_all=False)
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            # Get pool status safely
            pool_status = {'available_connections': 0, 'used_connections': 0}
            try:
                if self.connection_pool:
                    # For psycopg2 ThreadedConnectionPool, we need to check differently
                    with self.lock:
                        # Get pool stats indirectly by checking the internal attributes
                        total_connections = self.connection_pool.maxconn
                        # The pool doesn't expose used/available directly, so we provide basic info
                        pool_status = {
                            'total_connections': total_connections,
                            'min_connections': self.connection_pool.minconn,
                            'max_connections': self.connection_pool.maxconn,
                            'pool_initialized': True,
                            'keepalive_settings': {
                                'keepalives_idle': '600s',
                                'statement_timeout': '60s'
                            }
                        }
            except Exception as pool_error:
                logger.warning(f"Could not get detailed pool status: {str(pool_error)}")
                pool_status = {'pool_initialized': bool(self.connection_pool)}

            return {
                'status': 'healthy',
                'response_time_ms': round(response_time, 2),
                'server_time': result['server_time'].isoformat() if result and result['server_time'] else None,
                'pool_status': pool_status
            }

        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'response_time_ms': None,
                'server_time': None,
                'pool_status': {
                    'pool_initialized': False,
                    'error': 'Health check failed'
                }
            }

    def get_country_tier_analytics(self, country: str = None, region: str = None) -> Dict[str, Any]:
        """
        Get tier analytics data for a specific country or region with rankings and month-wise breakdown.

        Args:
            country (str, optional): Specific country to analyze
            region (str, optional): Specific region to analyze

        Returns:
            Dict: Comprehensive tier analytics with rankings and monthly data
        """
        try:
            # Determine filter condition
            filter_condition = ""
            filter_params = []

            if country:
                filter_condition = "AND pi.partner_country = %s"
                filter_params.append(country)
            elif region:
                filter_condition = "AND pi.partner_region = %s"
                filter_params.append(region)

            # Get overall country/region summary with rankings
            summary_query = f"""
            WITH country_totals AS (
                SELECT
                    pi.partner_country,
                    pi.partner_region,
                    COUNT(DISTINCT pi.partner_id) as total_partners,
                    COALESCE(SUM(cm.total_earnings), 0) as total_partner_earnings,
                    COALESCE(SUM(td.total_deposit), 0) as total_deposits,
                    COUNT(DISTINCT up.binary_user_id) as total_new_clients
                FROM partner.partner_info pi
                LEFT JOIN partner.commission_monthly cm ON pi.partner_id = cm.partner_id
                LEFT JOIN client.user_profile up ON pi.partner_id = up.affiliated_partner_id
                LEFT JOIN client.transaction_monthly tm ON up.binary_user_id = tm.binary_user_id
                LEFT JOIN (
                    SELECT
                        binary_user_id,
                        SUM(total_deposit) as total_deposit
                    FROM client.transaction_monthly
                    GROUP BY binary_user_id
                ) td ON up.binary_user_id = td.binary_user_id
                WHERE pi.is_internal = FALSE
                    AND pi.date_joined >= CURRENT_DATE - INTERVAL '12 months'
                    {filter_condition}
                GROUP BY pi.partner_country, pi.partner_region
            ),
            ranked_countries AS (
                SELECT *,
                    ROW_NUMBER() OVER (ORDER BY total_partner_earnings DESC) as earnings_rank,
                    ROW_NUMBER() OVER (ORDER BY total_deposits DESC) as deposits_rank,
                    ROW_NUMBER() OVER (ORDER BY total_new_clients DESC) as clients_rank,
                    ROW_NUMBER() OVER (ORDER BY total_partners DESC) as partners_rank
                FROM country_totals
            )
            SELECT
                partner_country,
                partner_region,
                total_partners,
                total_partner_earnings,
                total_deposits,
                total_new_clients,
                earnings_rank,
                deposits_rank,
                clients_rank,
                partners_rank
            FROM ranked_countries
            """

            if country or region:
                summary_query += " WHERE "
                if country:
                    summary_query += "partner_country = %s"
                else:
                    summary_query += "partner_region = %s"

            summary_results = self.execute_query(summary_query, filter_params)

            # Get monthly tier breakdown
            monthly_tier_query = f"""
            WITH monthly_tier_data AS (
                SELECT
                    DATE_TRUNC('month', cm.month)::date as month,
                    CASE
                        WHEN SUM(cm.total_earnings) >= 5000 THEN 'Platinum'
                        WHEN SUM(cm.total_earnings) >= 1000 THEN 'Gold'
                        WHEN SUM(cm.total_earnings) >= 100 THEN 'Silver'
                        WHEN SUM(cm.total_earnings) > 0 THEN 'Bronze'
                        ELSE 'Inactive'
                    END as partner_tier,
                    COUNT(DISTINCT pi.partner_id) as partner_count,
                    COALESCE(SUM(cm.total_earnings), 0) as total_earnings,
                    COALESCE(SUM(tm.expected_revenue), 0) as total_revenue,
                    COALESCE(SUM(td.total_deposit), 0) as total_deposits,
                    COUNT(DISTINCT up.binary_user_id) as new_clients
                FROM partner.partner_info pi
                LEFT JOIN partner.commission_monthly cm ON pi.partner_id = cm.partner_id
                LEFT JOIN client.user_profile up ON pi.partner_id = up.affiliated_partner_id
                LEFT JOIN client.trade_monthly tm ON up.binary_user_id = tm.binary_user_id
                    AND DATE_TRUNC('month', tm.month) = DATE_TRUNC('month', cm.month)
                LEFT JOIN (
                    SELECT
                        binary_user_id,
                        DATE_TRUNC('month', transaction_month)::date as month,
                        SUM(total_deposit) as total_deposit
                    FROM client.transaction_monthly
                    GROUP BY binary_user_id, DATE_TRUNC('month', transaction_month)::date
                ) td ON up.binary_user_id = td.binary_user_id
                    AND td.month = DATE_TRUNC('month', cm.month)::date
                WHERE pi.is_internal = FALSE
                    AND cm.month >= CURRENT_DATE - INTERVAL '12 months'
                    {filter_condition}
                GROUP BY pi.partner_id, DATE_TRUNC('month', cm.month)::date
            )
            SELECT
                month,
                partner_tier,
                SUM(partner_count) as tier_count,
                SUM(total_earnings) as tier_earnings,
                SUM(total_revenue) as tier_revenue,
                SUM(total_deposits) as tier_deposits,
                SUM(new_clients) as tier_new_clients
            FROM monthly_tier_data
            GROUP BY month, partner_tier
            ORDER BY month DESC,
                CASE partner_tier
                    WHEN 'Platinum' THEN 1
                    WHEN 'Gold' THEN 2
                    WHEN 'Silver' THEN 3
                    WHEN 'Bronze' THEN 4
                    WHEN 'Inactive' THEN 5
                END
            """

            tier_results = self.execute_query(monthly_tier_query, filter_params)

            # Format monthly tier data for frontend
            monthly_data = {}
            for row in tier_results:
                month_str = row['month'].strftime('%b %Y') if row['month'] else 'Unknown'
                if month_str not in monthly_data:
                    monthly_data[month_str] = {}

                tier = row['partner_tier']
                monthly_data[month_str][tier] = {
                    'count': int(row['tier_count']) if row['tier_count'] else 0,
                    'earnings': float(row['tier_earnings']) if row['tier_earnings'] else 0,
                    'revenue': float(row['tier_revenue']) if row['tier_revenue'] else 0,
                    'deposits': float(row['tier_deposits']) if row['tier_deposits'] else 0,
                    'new_clients': int(row['tier_new_clients']) if row['tier_new_clients'] else 0
                }

            # Get country application ranking data
            ranking_query = """
            SELECT
                pi.partner_country,
                DATE_TRUNC('month', pi.date_joined)::date as application_month,
                COUNT(DISTINCT pi.partner_id) as applications,
                ROW_NUMBER() OVER (
                    PARTITION BY DATE_TRUNC('month', pi.date_joined)::date
                    ORDER BY COUNT(DISTINCT pi.partner_id) DESC
                ) as rank
            FROM partner.partner_info pi
            WHERE pi.is_internal = FALSE
                AND pi.date_joined >= CURRENT_DATE - INTERVAL '12 months'
                AND pi.partner_country IS NOT NULL
            GROUP BY pi.partner_country, DATE_TRUNC('month', pi.date_joined)::date
            ORDER BY application_month DESC, rank ASC
            """

            ranking_results = self.execute_query(ranking_query)

            # Format ranking data
            country_rankings = {}
            for row in ranking_results:
                month_str = row['application_month'].strftime('%b %Y') if row['application_month'] else 'Unknown'
                country = row['partner_country']
                if month_str not in country_rankings:
                    country_rankings[month_str] = {}
                country_rankings[month_str][country] = {
                    'applications': int(row['applications']),
                    'rank': int(row['rank'])
                }

            logger.info(f"Retrieved tier analytics for {'country: ' + country if country else 'region: ' + region if region else 'all countries'}")

            return {
                'summary': summary_results[0] if summary_results and len(summary_results) > 0 else {},
                'monthly_tier_data': monthly_data,
                'country_rankings': country_rankings,
                'available_months': sorted(monthly_data.keys(), reverse=True) if monthly_data else []
            }

        except Exception as e:
            logger.error(f"Error fetching country tier analytics: {str(e)}")
            return {
                'summary': {},
                'monthly_tier_data': {},
                'country_rankings': {},
                'available_months': []
            }

    def get_tier_detail_data(self, country: str = None, region: str = None, tier: str = None, month: str = None) -> List[Dict[str, Any]]:
        """
        Get detailed tier performance data with rankings for tier detail modal.

        Args:
            country (str, optional): Specific country
            region (str, optional): Specific region
            tier (str, optional): Specific tier (Platinum, Gold, Silver, Bronze, Inactive)
            month (str, optional): Specific month in 'YYYY-MM' format

        Returns:
            List[Dict]: Detailed tier performance with rankings
        """
        try:
            # Build filter conditions
            filter_conditions = ["pi.is_internal = FALSE"]
            filter_params = []

            if country:
                filter_conditions.append("pi.partner_country = %s")
                filter_params.append(country)
            elif region:
                filter_conditions.append("pi.partner_region = %s")
                filter_params.append(region)

            if month:
                filter_conditions.append("DATE_TRUNC('month', cm.month)::date = %s")
                try:
                    from datetime import datetime
                    parsed_date = datetime.strptime(f"{month}-01", '%Y-%m-%d')
                    filter_params.append(parsed_date.date())
                except ValueError:
                    logger.warning(f"Invalid month format: {month}")

            # Add tier filter if specified
            tier_case = """
                CASE
                    WHEN SUM(cm.total_earnings) >= 5000 THEN 'Platinum'
                    WHEN SUM(cm.total_earnings) >= 1000 THEN 'Gold'
                    WHEN SUM(cm.total_earnings) >= 100 THEN 'Silver'
                    WHEN SUM(cm.total_earnings) > 0 THEN 'Bronze'
                    ELSE 'Inactive'
                END
            """

            query = f"""
            WITH partner_performance AS (
                SELECT
                    DATE_TRUNC('month', cm.month)::date as month,
                    pi.partner_id,
                    pi.partner_country,
                    pi.partner_region,
                    {tier_case} as partner_tier,
                    COALESCE(SUM(cm.total_earnings), 0) as total_earnings,
                    COALESCE(SUM(tm.expected_revenue), 0) as company_revenue,
                    COALESCE(SUM(td.total_deposit), 0) as total_deposits,
                    COUNT(DISTINCT up.binary_user_id) as active_clients,
                    COUNT(DISTINCT CASE WHEN up.real_joined_date >= DATE_TRUNC('month', cm.month)
                        AND up.real_joined_date < DATE_TRUNC('month', cm.month) + INTERVAL '1 month'
                        THEN up.binary_user_id END) as new_clients,
                    COALESCE(SUM(tm.volume_usd), 0) as volume,
                    CASE
                        WHEN SUM(tm.expected_revenue) > 0
                        THEN (SUM(cm.total_earnings) / SUM(tm.expected_revenue)) * 100
                        ELSE 0
                    END as etr_ratio,
                    CASE
                        WHEN SUM(td.total_deposit) > 0
                        THEN (SUM(cm.total_earnings) / SUM(td.total_deposit)) * 100
                        ELSE 0
                    END as etd_ratio
                FROM partner.partner_info pi
                LEFT JOIN partner.commission_monthly cm ON pi.partner_id = cm.partner_id
                LEFT JOIN client.user_profile up ON pi.partner_id = up.affiliated_partner_id
                LEFT JOIN client.trade_monthly tm ON up.binary_user_id = tm.binary_user_id
                    AND DATE_TRUNC('month', tm.month) = DATE_TRUNC('month', cm.month)
                LEFT JOIN (
                    SELECT
                        binary_user_id,
                        DATE_TRUNC('month', transaction_month)::date as month,
                        SUM(total_deposit) as total_deposit
                    FROM client.transaction_monthly
                    GROUP BY binary_user_id, DATE_TRUNC('month', transaction_month)::date
                ) td ON up.binary_user_id = td.binary_user_id
                    AND td.month = DATE_TRUNC('month', cm.month)::date
                WHERE {' AND '.join(filter_conditions)}
                    AND cm.month >= CURRENT_DATE - INTERVAL '12 months'
                GROUP BY pi.partner_id, pi.partner_country, pi.partner_region, DATE_TRUNC('month', cm.month)::date
            ),
            ranked_performance AS (
                SELECT *,
                    ROW_NUMBER() OVER (PARTITION BY month, partner_tier ORDER BY total_earnings DESC) as earnings_rank,
                    ROW_NUMBER() OVER (PARTITION BY month, partner_tier ORDER BY company_revenue DESC) as revenue_rank,
                    ROW_NUMBER() OVER (PARTITION BY month, partner_tier ORDER BY total_deposits DESC) as deposits_rank,
                    ROW_NUMBER() OVER (PARTITION BY month, partner_tier ORDER BY active_clients DESC) as clients_rank,
                    ROW_NUMBER() OVER (PARTITION BY month, partner_tier ORDER BY new_clients DESC) as new_clients_rank,
                    ROW_NUMBER() OVER (PARTITION BY month, partner_tier ORDER BY volume DESC) as volume_rank
                FROM partner_performance
            )
            SELECT
                month,
                partner_tier,
                total_earnings,
                company_revenue,
                etr_ratio,
                total_deposits,
                etd_ratio,
                active_clients,
                new_clients,
                volume,
                earnings_rank,
                revenue_rank,
                deposits_rank,
                clients_rank,
                new_clients_rank,
                volume_rank
            FROM ranked_performance
            """

            if tier:
                query += f" WHERE partner_tier = %s"
                filter_params.append(tier)

            query += " ORDER BY month DESC, earnings_rank ASC"

            results = self.execute_query(query, filter_params)

            # Format results
            formatted_results = []
            for row in results:
                formatted_results.append({
                    'month': row['month'].strftime('%b %Y') if row['month'] else 'Unknown',
                    'tier': row['partner_tier'],
                    'total_earnings': float(row['total_earnings']),
                    'earnings_rank': int(row['earnings_rank']),
                    'company_revenue': float(row['company_revenue']),
                    'revenue_rank': int(row['revenue_rank']),
                    'etr_ratio': round(float(row['etr_ratio']), 2),
                    'total_deposits': float(row['total_deposits']),
                    'deposits_rank': int(row['deposits_rank']),
                    'etd_ratio': round(float(row['etd_ratio']), 2),
                    'active_clients': int(row['active_clients']),
                    'clients_rank': int(row['clients_rank']),
                    'new_clients': int(row['new_clients']),
                    'new_clients_rank': int(row['new_clients_rank']),
                    'volume': float(row['volume']),
                    'volume_rank': int(row['volume_rank'])
                })

            logger.info(f"Retrieved tier detail data: {len(formatted_results)} records")
            return formatted_results

        except Exception as e:
            logger.error(f"Error fetching tier detail data: {str(e)}")
            return []

    def get_monthly_country_funnel_data(self, country: str = None, region: str = None) -> Dict[str, Any]:
        """
        Get monthly funnel data for a specific country/region showing all months with rankings.

        Args:
            country (str, optional): Specific country
            region (str, optional): Specific region

        Returns:
            Dict: Monthly funnel data with rankings
        """
        try:
            # Build filter condition
            filter_condition = ""
            filter_params = []

            if country:
                filter_condition = "AND pi.partner_country = %s"
                filter_params.append(country)
            elif region:
                filter_condition = "AND pi.partner_region = %s"
                filter_params.append(region)

            # Get monthly data with rankings - fixed for regions
            if country:
                # For countries: original logic
                query = f"""
                WITH monthly_data AS (
                    SELECT
                        DATE_TRUNC('month', pi.date_joined)::date as application_month,
                        COUNT(DISTINCT pi.partner_id) as total_applications,
                        COUNT(DISTINCT CASE WHEN pi.first_client_joined_date IS NOT NULL THEN pi.partner_id END) as client_activated,
                        COUNT(DISTINCT CASE WHEN pi.first_earning_date IS NOT NULL THEN pi.partner_id END) as earning_activated,
                        COUNT(DISTINCT CASE WHEN pi.parent_partner_id IS NOT NULL THEN pi.partner_id END) as sub_partners,
                        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (
                            CASE WHEN pi.first_client_joined_date IS NOT NULL
                            THEN (pi.first_client_joined_date - pi.date_joined)
                            END
                        ))::NUMERIC, 1) as avg_days_to_first_client,
                        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (
                            CASE WHEN pi.first_earning_date IS NOT NULL
                            THEN (pi.first_earning_date - pi.date_joined)
                            END
                        ))::NUMERIC, 1) as avg_days_to_first_earning
                    FROM partner.partner_info pi
                    WHERE pi.is_internal = FALSE
                        AND pi.date_joined >= CURRENT_DATE - INTERVAL '12 months'
                        AND pi.partner_country = %s
                    GROUP BY DATE_TRUNC('month', pi.date_joined)::date
                ),
                all_countries_monthly AS (
                    SELECT
                        pi.partner_country,
                        DATE_TRUNC('month', pi.date_joined)::date as application_month,
                        COUNT(DISTINCT pi.partner_id) as applications
                    FROM partner.partner_info pi
                    WHERE pi.is_internal = FALSE
                        AND pi.date_joined >= CURRENT_DATE - INTERVAL '12 months'
                        AND pi.partner_country IS NOT NULL
                    GROUP BY pi.partner_country, DATE_TRUNC('month', pi.date_joined)::date
                ),
                ranked_countries AS (
                    SELECT *,
                        ROW_NUMBER() OVER (PARTITION BY application_month ORDER BY applications DESC) as rank
                    FROM all_countries_monthly
                )
                SELECT
                    md.application_month,
                    md.total_applications,
                    md.client_activated,
                    md.earning_activated,
                    md.sub_partners,
                    md.avg_days_to_first_client,
                    md.avg_days_to_first_earning,
                    COALESCE(rc.rank, 0) as country_rank
                FROM monthly_data md
                LEFT JOIN ranked_countries rc ON md.application_month = rc.application_month
                    AND rc.partner_country = %s
                ORDER BY md.application_month DESC
                """
                filter_params = [country, country]
            else:
                # For regions: aggregate countries within region and rank against other regions
                query = f"""
                WITH region_countries AS (
                    SELECT DISTINCT partner_country
                    FROM partner.partner_info
                    WHERE partner_region = %s
                        AND partner_country IS NOT NULL
                        AND partner_country != ''
                ),
                monthly_data AS (
                    SELECT
                        DATE_TRUNC('month', pi.date_joined)::date as application_month,
                        COUNT(DISTINCT pi.partner_id) as total_applications,
                        COUNT(DISTINCT CASE WHEN pi.first_client_joined_date IS NOT NULL THEN pi.partner_id END) as client_activated,
                        COUNT(DISTINCT CASE WHEN pi.first_earning_date IS NOT NULL THEN pi.partner_id END) as earning_activated,
                        COUNT(DISTINCT CASE WHEN pi.parent_partner_id IS NOT NULL THEN pi.partner_id END) as sub_partners,
                        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (
                            CASE WHEN pi.first_client_joined_date IS NOT NULL
                            THEN (pi.first_client_joined_date - pi.date_joined)
                            END
                        ))::NUMERIC, 1) as avg_days_to_first_client,
                        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (
                            CASE WHEN pi.first_earning_date IS NOT NULL
                            THEN (pi.first_earning_date - pi.date_joined)
                            END
                        ))::NUMERIC, 1) as avg_days_to_first_earning
                    FROM partner.partner_info pi
                    INNER JOIN region_countries rc ON pi.partner_country = rc.partner_country
                    WHERE pi.is_internal = FALSE
                        AND pi.date_joined >= CURRENT_DATE - INTERVAL '12 months'
                    GROUP BY DATE_TRUNC('month', pi.date_joined)::date
                ),
                all_regions_monthly AS (
                    SELECT
                        pi.partner_region,
                        DATE_TRUNC('month', pi.date_joined)::date as application_month,
                        COUNT(DISTINCT pi.partner_id) as applications
                    FROM partner.partner_info pi
                    WHERE pi.is_internal = FALSE
                        AND pi.date_joined >= CURRENT_DATE - INTERVAL '12 months'
                        AND pi.partner_region IS NOT NULL
                    GROUP BY pi.partner_region, DATE_TRUNC('month', pi.date_joined)::date
                ),
                ranked_regions AS (
                    SELECT *,
                        ROW_NUMBER() OVER (PARTITION BY application_month ORDER BY applications DESC) as rank
                    FROM all_regions_monthly
                )
                SELECT
                    md.application_month,
                    md.total_applications,
                    md.client_activated,
                    md.earning_activated,
                    md.sub_partners,
                    md.avg_days_to_first_client,
                    md.avg_days_to_first_earning,
                    COALESCE(rr.rank, 0) as country_rank
                FROM monthly_data md
                LEFT JOIN ranked_regions rr ON md.application_month = rr.application_month
                    AND rr.partner_region = %s
                ORDER BY md.application_month DESC
                """
                filter_params = [region, region]

            results = self.execute_query(query, filter_params)

            # Format results
            monthly_data = []
            for row in results:
                monthly_data.append({
                    'month': row['application_month'].strftime('%b %Y') if row['application_month'] else 'Unknown',
                    'applications': int(row['total_applications']),
                    'partners_activated': int(row['client_activated']),
                    'partners_earning': int(row['earning_activated']),
                    'sub_partners': int(row['sub_partners']),
                    'days_to_client': float(row['avg_days_to_first_client']) if row['avg_days_to_first_client'] else 0,
                    'days_to_earning': float(row['avg_days_to_first_earning']) if row['avg_days_to_first_earning'] else 0,
                    'country_rank': int(row['country_rank']) if row['country_rank'] else 0,
                    'client_activation_rate': round((int(row['client_activated']) / int(row['total_applications']) * 100), 1) if int(row['total_applications']) > 0 else 0,
                    'earning_activation_rate': round((int(row['earning_activated']) / int(row['total_applications']) * 100), 1) if int(row['total_applications']) > 0 else 0
                })

            logger.info(f"Retrieved monthly country funnel data: {len(monthly_data)} months")
            return {
                'monthly_data': monthly_data,
                'total_months': len(monthly_data)
            }

        except Exception as e:
            logger.error(f"Error fetching monthly country funnel data: {str(e)}")
            return {
                'monthly_data': [],
                'total_months': 0
            }

# Global database instance
db = SupabaseDB()