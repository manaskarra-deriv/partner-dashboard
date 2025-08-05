import React, { useState, useEffect } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import { API_BASE_URL } from './config';
import './App.css';

// Components
import Dashboard from './components/Dashboard';
import PartnerDetailPage from './components/PartnerDetailPage';
import LoadingScreen from './components/LoadingScreen';
import ApplicationFunnel from './components/ApplicationFunnel';

function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const [partners, setPartners] = useState([]);
  const [overview, setOverview] = useState(null);
  const [tierAnalytics, setTierAnalytics] = useState(null);
  const [filters, setFilters] = useState({});
  const [activeFilters, setActiveFilters] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sortField, setSortField] = useState('total_earnings');
  const [sortDirection, setSortDirection] = useState('desc');
  
  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const partnersPerPage = 30;
  
  // PII Privacy state
  const [showPII, setShowPII] = useState(false);

  // Add state for password modal
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [passwordInput, setPasswordInput] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [pendingAction, setPendingAction] = useState(null); // Store action to execute after password verification

  // Check if we're on a partner detail page
  const isPartnerDetailPage = location.pathname.startsWith('/partner/');

  // Handle partner navigation from tier progression modal
  useEffect(() => {
    const handleSwitchToPartnerManagement = (event) => {
      const { partnerId } = event.detail;
      
      // Navigate to the partner detail page using React Router
      navigate(`/partner/${partnerId}`);
    };

    window.addEventListener('switchToPartnerManagement', handleSwitchToPartnerManagement);

    return () => {
      window.removeEventListener('switchToPartnerManagement', handleSwitchToPartnerManagement);
    };
  }, [navigate]);

  // Helper function to navigate to partner detail
  const navigateToPartnerDetail = (partnerId) => {
    // Navigate to the partner detail page using React Router
    navigate(`/partner/${partnerId}`);
  };

  // Loading states for different modules
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [funnelLoading, setFunnelLoading] = useState(true);
  const [partnerMgmtLoading, setPartnerMgmtLoading] = useState(true);
  const [funnelData, setFunnelData] = useState(null);
  const [availableCountries, setAvailableCountries] = useState([]);
  const [availableRegions, setAvailableRegions] = useState([]);
  
  // Country Analysis persistent state
  const [tierAnalyticsDataCountry, setTierAnalyticsDataCountry] = useState(null);
  const [monthlyCountryData, setMonthlyCountryData] = useState(null);
  const [tierProgressionData, setTierProgressionData] = useState(null);
  const [selectedCountry, setSelectedCountry] = useState('');
  const [selectedRegion, setSelectedRegion] = useState('');
  const [countryAnalysisLoading, setCountryAnalysisLoading] = useState({
    tier: false,
    monthly: false,
    progression: false
  });
  const [funnelInitialLoading, setFunnelInitialLoading] = useState(true);

  // Separate loading states for performance analytics and tier analytics
  const [performanceAnalyticsLoading, setPerformanceAnalyticsLoading] = useState(true);
  const [tierAnalyticsLoading, setTierAnalyticsLoading] = useState(true);
  
  // Separate the data states
  const [performanceAnalyticsData, setPerformanceAnalyticsData] = useState(null);
  const [tierAnalyticsData, setTierAnalyticsData] = useState(null);

  // Add state for active tab
  const [activeTab, setActiveTab] = useState('overview');

  // Fetch all three modules in parallel on mount
  useEffect(() => {
    fetchOverview();
    fetchPartners(activeFilters, 1);
    fetchFilters();
    fetchTierAnalytics();
    // Simulate Partner Management loading
    setPartnerMgmtLoading(true);
    setTimeout(() => setPartnerMgmtLoading(false), 1200);
    // Fetch Application Funnel initial data
    setFunnelInitialLoading(true);
    Promise.all([
      fetchInitialFunnelData(),
      fetchAvailableCountriesAndRegions()
    ]).then(() => setFunnelInitialLoading(false));
  }, []);

  // Handle scroll restoration when returning from partner detail
  useEffect(() => {
    // Check if we're returning from partner detail with saved state
    if (location.pathname === '/' && location.state?.scrollPosition !== undefined) {
      const { scrollPosition, savedFilters, savedPage, savedSortField, savedSortDirection, savedTab } = location.state;
      
      // Restore state if it was passed
      if (savedFilters) setActiveFilters(savedFilters);
      if (savedPage) setCurrentPage(savedPage);
      if (savedSortField) setSortField(savedSortField);
      if (savedSortDirection) setSortDirection(savedSortDirection);
      if (savedTab) setActiveTab(savedTab); // Restore the tab
      
      // Refetch data with restored state
      if (savedFilters !== undefined && savedPage !== undefined) {
        fetchPartners(savedFilters, savedPage);
      }
      
      // Store scroll position for restoration after loading
      window._pendingScrollPosition = scrollPosition;
      
      // Clear the state from location to prevent re-triggering
      window.history.replaceState({}, document.title, location.pathname);
    }
  }, [location]);

  // Restore scroll position when loading completes
  useEffect(() => {
    if (!loading && window._pendingScrollPosition !== undefined) {
      setTimeout(() => {
        window.scrollTo({ top: window._pendingScrollPosition, behavior: 'instant' });
        delete window._pendingScrollPosition;
      }, 100);
    }
  }, [loading]);

  // Refetch partners when sorting changes (reset to page 1)
  useEffect(() => {
    setCurrentPage(1);
    fetchPartners(activeFilters, 1);
  }, [sortField, sortDirection]);

  const fetchOverview = async () => {
    setOverviewLoading(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/api/partner-overview`);
      setOverview(response.data);
    } catch (err) {
      console.error('Error fetching overview:', err);
      setError('Failed to load partner overview');
    } finally {
      setOverviewLoading(false);
    }
  };

  const fetchPartners = async (filterParams = {}, page = currentPage) => {
    try {
      setLoading(true);
      const offset = (page - 1) * partnersPerPage;
      const params = {
        ...filterParams,
        sort_by: sortField,
        sort_order: sortDirection,
        limit: partnersPerPage,
        offset: offset
      };
      const response = await axios.get(`${API_BASE_URL}/api/partners`, { params });
      setPartners(response.data.partners);
      setTotalCount(response.data.total_count);
      setHasMore(response.data.has_more);
    } catch (err) {
      console.error('Error fetching partners:', err);
      setError('Failed to load partners');
    } finally {
      setLoading(false);
    }
  };

  const fetchFilters = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/filters`);
      setFilters(response.data);
    } catch (err) {
      console.error('Error fetching filters:', err);
    }
  };

  const fetchTierAnalytics = async () => {
    setPerformanceAnalyticsLoading(true);
    setTierAnalyticsLoading(true);
    try {
      // Add cache busting parameter to ensure fresh data
      const cacheBuster = `?t=${Date.now()}`;
      const response = await axios.get(`${API_BASE_URL}/api/tier-analytics${cacheBuster}`);
      const data = response.data;
      
      // Set performance analytics data (monthly_charts and totals only)
      const performanceData = {
        monthly_charts: data.monthly_charts,
        totals: data.totals
      };
      setPerformanceAnalyticsData(performanceData);
      setPerformanceAnalyticsLoading(false);
      
      // Set tier analytics data (tier_summary and totals)
      const tierData = {
        tier_summary: data.tier_summary,
        totals: data.totals
      };
      setTierAnalyticsData(tierData);
      setTierAnalyticsLoading(false);
      
      // Keep the original tierAnalytics for backward compatibility
      setTierAnalytics(data);
    } catch (err) {
      console.error('Error fetching tier analytics:', err);
      setError('Failed to load tier analytics');
      setPerformanceAnalyticsLoading(false);
      setTierAnalyticsLoading(false);
    } finally {
      setFunnelLoading(false);
    }
  };

  // Fetch initial funnel data
  const fetchInitialFunnelData = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/partner-application-funnel`);
      setFunnelData(response.data);
    } catch (err) {
      // Optionally handle error
    }
  };

  // Fetch available countries and regions
  const fetchAvailableCountriesAndRegions = async () => {
    try {
      // Fetch countries from the countries endpoint
      const countriesResponse = await axios.get(`${API_BASE_URL}/api/partner-application-countries`);
      setAvailableCountries(countriesResponse.data.countries || []);

      // Fetch regions from the filters endpoint (always returns regions)
      const filtersResponse = await axios.get(`${API_BASE_URL}/api/filters`);
      setAvailableRegions(filtersResponse.data.regions || []);
    } catch (err) {
      // Optionally handle error
    }
  };

  // Progress calculation for splash
  const modulesLoaded = [!overviewLoading, !funnelLoading, !partnerMgmtLoading, !funnelInitialLoading, !performanceAnalyticsLoading, !tierAnalyticsLoading].filter(Boolean).length;
  const progress = Math.round((modulesLoaded / 6) * 100);
  const allLoaded = modulesLoaded === 6;

  // Show splash screen with progress bar until all loaded
  if (!allLoaded) {
    return <LoadingScreen fullscreen progress={progress} />;
  }

  const handleFilterChange = (newFilters) => {
    // Don't change scroll position when filters change - keep user where they are
    setActiveFilters(newFilters);
    setCurrentPage(1);
    fetchPartners(newFilters, 1);
  };

  const handlePageChange = (newPage) => {
    setCurrentPage(newPage);
    fetchPartners(activeFilters, newPage);
  };

  const totalPages = Math.ceil(totalCount / partnersPerPage);

  const handleSortChange = (field) => {
    let newDirection = 'desc';
    if (sortField === field && sortDirection === 'desc') {
      newDirection = 'asc';
    }
    setSortField(field);
    setSortDirection(newDirection);
  };

  const handlePartnerSelect = (partner) => {
    // Capture current state before navigation
    const currentScrollPosition = window.pageYOffset || document.documentElement.scrollTop;
    const currentState = {
      scrollPosition: currentScrollPosition,
      savedFilters: activeFilters,
      savedPage: currentPage,
      savedSortField: sortField,
      savedSortDirection: sortDirection,
      savedTab: activeTab // Save the current tab
    };
    
    navigate(`/partner/${partner.partner_id}`, { state: currentState });
  };

  const handleBackToDashboard = () => {
    // Use saved state from navigation if available
    const savedState = location.state;
    if (savedState) {
      navigate('/', { state: savedState });
    } else {
      navigate('/');
    }
  };

  const formatCurrency = (amount, exact = false, smart = false) => {
    if (smart && amount >= 1000000) {
      // For smart abbreviation in overview cards
      if (amount >= 1000000000) {
        return `$${(amount / 1000000000).toFixed(1)}B`;
      } else {
        return `$${(amount / 1000000).toFixed(1)}M`;
      }
    }
    
    const number = Number(amount);
    
    if (exact) {
      // For exact formatting (detail pages)
      if (number % 1 === 0) {
        return new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
          minimumFractionDigits: 0,
          maximumFractionDigits: 0,
        }).format(number);
      } else {
        return new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        }).format(number);
      }
    } else {
      // For standard formatting (most places)
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      }).format(number);
    }
  };

  const formatVolume = (amount) => {
    const number = Number(amount);
    
    if (number >= 1000000000000) {
      // Trillion
      return `$${(number / 1000000000000).toFixed(2)}T`;
    } else if (number >= 1000000000) {
      // Billion
      return `$${(number / 1000000000).toFixed(2)}B`;
    } else if (number >= 1000000) {
      // Million
      return `$${(number / 1000000).toFixed(2)}M`;
    } else if (number >= 1000) {
      // Thousand
      return `$${(number / 1000).toFixed(1)}K`;
    } else {
      // Less than thousand
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      }).format(number);
    }
  };

  const formatNumber = (num, exact = false) => {
    const number = Number(num);
    
    if (exact) {
      // For exact formatting (overview cards)
      if (number % 1 === 0) {
        // Whole number - no decimals
        return new Intl.NumberFormat('en-US', {
          minimumFractionDigits: 0,
          maximumFractionDigits: 0,
        }).format(number);
      } else {
        // Has decimals - show exactly 2 decimal places
        return new Intl.NumberFormat('en-US', {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        }).format(number);
      }
    } else {
      // For abbreviated formatting (tables, other places)
      const rounded = Math.round(number);
      const absRounded = Math.abs(rounded);
      const sign = rounded < 0 ? '-' : '';
      
      if (absRounded >= 1000000000000) {
        return `${sign}${(absRounded / 1000000000000).toFixed(1)}T`;
      } else if (absRounded >= 1000000000) {
        return `${sign}${(absRounded / 1000000000).toFixed(1)}B`;
      } else if (absRounded >= 1000000) {
        return `${sign}${(absRounded / 1000000).toFixed(1)}M`;
      } else if (absRounded >= 1000) {
        return `${sign}${(absRounded / 1000).toFixed(1)}K`;
      } else {
        return new Intl.NumberFormat('en-US', {
          minimumFractionDigits: 0,
          maximumFractionDigits: 0,
        }).format(rounded);
      }
    }
  };

  const getTierColor = (tier) => {
    const colors = {
      'Platinum': 'platinum',
      'Gold': 'gold',
      'Silver': 'silver',
      'Bronze': 'bronze',
      'Inactive': 'inactive'
    };
    return colors[tier] || 'inactive';
  };

  // Add handler for password submit
  function handlePasswordSubmit() {
    if (passwordInput === process.env.REACT_APP_PII_PASSWORD) {
      setShowPII(true);
      setShowPasswordModal(false);
      setPasswordInput("");
      setPasswordError("");
      // Execute pending action if any
      if (pendingAction) {
        pendingAction();
        setPendingAction(null);
      }
    } else {
      setPasswordError('Incorrect password.');
    }
  }

  // Add handler for requesting PII access
  const handleRequestPIIAccess = (actionToExecute) => {
    setPendingAction(() => actionToExecute);
    setShowPasswordModal(true);
  };

  if (error) {
    return (
      <div className="app-container">
        <div className="error-state">
          <div className="error-content">
            <h2>Something went wrong</h2>
            <p>{error}</p>
            <button className="btn-primary" onClick={() => window.location.reload()}>
              Reload Page
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* Password Modal */}
      {showPasswordModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh',
          background: 'rgba(0,0,0,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div style={{ background: 'white', padding: 24, borderRadius: 8, minWidth: 300, boxShadow: '0 2px 8px rgba(0,0,0,0.2)' }}>
            <h3>Enter password to show PII</h3>
            <input
              type="password"
              value={passwordInput}
              onChange={e => { setPasswordInput(e.target.value); setPasswordError(""); }}
              style={{ width: '100%', padding: 8, marginTop: 8, marginBottom: 8, fontSize: 16 }}
              autoFocus
              onKeyDown={e => { if (e.key === 'Enter') handlePasswordSubmit(); }}
            />
            {passwordError && <div style={{ color: 'red', marginBottom: 8 }}>{passwordError}</div>}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button onClick={() => { setShowPasswordModal(false); setPasswordInput(""); setPasswordError(""); setPendingAction(null); }} style={{ padding: '6px 16px' }}>Cancel</button>
              <button onClick={handlePasswordSubmit} style={{ padding: '6px 16px' }}>Submit</button>
            </div>
          </div>
        </div>
      )}
      {/* Header */}
      <header className="header">
        <div className="header-content">
          <div className="header-left">
            {isPartnerDetailPage && (
              <button 
                className="back-button"
                onClick={handleBackToDashboard}
                title="Back to Dashboard"
              >
                ←
              </button>
            )}
            <img src="/Deriv.png" alt="Deriv" className="logo" />
            <h1 className="heading-lg">Partner Performance Analysis & Management Tool</h1>
          </div>
          <div className="header-right">
            <button 
              className={`pii-toggle ${showPII ? 'pii-visible' : 'pii-hidden'}`}
              onClick={() => {
                if (!showPII) {
                  setShowPasswordModal(true);
                } else {
                  setShowPII(false);
                }
              }}
              title={showPII ? 'Hide PII Data' : 'Show PII Data'}
            >
              <span className="pii-icon">{showPII ? '👁️' : '🔒'}</span>
              <span className="pii-text">{showPII ? 'Hide PII' : 'Show PII'}</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="main-content">
        <Routes>
          <Route path="/" element={
            <Dashboard
              overview={overview}
              tierAnalytics={tierAnalytics}
              partners={partners}
              filters={filters}
              activeFilters={activeFilters}
              loading={loading}
              onFilterChange={handleFilterChange}
              onPartnerSelect={handlePartnerSelect}
              formatCurrency={formatCurrency}
              formatNumber={formatNumber}
              formatVolume={formatVolume}
              getTierColor={getTierColor}
              sortField={sortField}
              sortDirection={sortDirection}
              onSortChange={handleSortChange}
              showPII={showPII}
              // Pagination props
              currentPage={currentPage}
              totalPages={totalPages}
              totalCount={totalCount}
              partnersPerPage={partnersPerPage}
              onPageChange={handlePageChange}
              funnelData={funnelData}
              availableCountries={availableCountries}
              availableRegions={availableRegions}
              activeTab={activeTab}
              setActiveTab={setActiveTab}
              performanceAnalyticsLoading={performanceAnalyticsLoading}
              tierAnalyticsLoading={tierAnalyticsLoading}
              performanceAnalyticsData={performanceAnalyticsData}
              tierAnalyticsData={tierAnalyticsData}
              onRequestPIIAccess={handleRequestPIIAccess}
              navigateToPartnerDetail={navigateToPartnerDetail}
              // Persistent country analysis state
              tierAnalyticsDataCountry={tierAnalyticsDataCountry}
              setTierAnalyticsDataCountry={setTierAnalyticsDataCountry}
              monthlyCountryData={monthlyCountryData}
              setMonthlyCountryData={setMonthlyCountryData}
              tierProgressionData={tierProgressionData}
              setTierProgressionData={setTierProgressionData}
              selectedCountry={selectedCountry}
              setSelectedCountry={setSelectedCountry}
              selectedRegion={selectedRegion}
              setSelectedRegion={setSelectedRegion}
              countryAnalysisLoading={countryAnalysisLoading}
              setCountryAnalysisLoading={setCountryAnalysisLoading}
            />
          } />
          <Route path="/partner/:partnerId" element={
            <PartnerDetailPage
              formatCurrency={formatCurrency}
              formatNumber={formatNumber}
              formatVolume={formatVolume}
              getTierColor={getTierColor}
              onBack={handleBackToDashboard}
              showPII={showPII}
            />
          } />
        </Routes>
      </main>
    </div>
  );
}

export default App; 