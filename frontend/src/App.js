import React, { useState, useEffect } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import './App.css';

// Components
import Dashboard from './components/Dashboard';
import PartnerDetailPage from './components/PartnerDetailPage';
import LoadingScreen from './components/LoadingScreen';

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

  // Fetch initial data
  useEffect(() => {
    fetchOverview();
    fetchPartners(activeFilters, 1);
    fetchFilters();
    fetchTierAnalytics();
  }, []);

  // Handle scroll restoration when returning from partner detail
  useEffect(() => {
    // Check if we're returning from partner detail with saved state
    if (location.pathname === '/' && location.state?.scrollPosition !== undefined) {
      const { scrollPosition, savedFilters, savedPage, savedSortField, savedSortDirection } = location.state;
      
      // Restore state if it was passed
      if (savedFilters) setActiveFilters(savedFilters);
      if (savedPage) setCurrentPage(savedPage);
      if (savedSortField) setSortField(savedSortField);
      if (savedSortDirection) setSortDirection(savedSortDirection);
      
      // Refetch data with restored state
      if (savedFilters !== undefined && savedPage !== undefined) {
        fetchPartners(savedFilters, savedPage);
      }
      
      // Restore scroll position after the page renders and data loads
      setTimeout(() => {
        window.scrollTo(0, scrollPosition);
      }, 150);
      
      // Clear the state from location to prevent re-triggering
      window.history.replaceState({}, document.title, location.pathname);
    }
  }, [location]);

  // Refetch partners when sorting changes (reset to page 1)
  useEffect(() => {
    setCurrentPage(1);
    fetchPartners(activeFilters, 1);
  }, [sortField, sortDirection]);

  const fetchOverview = async () => {
    try {
      const response = await axios.get('/api/partner-overview');
      setOverview(response.data);
    } catch (err) {
      console.error('Error fetching overview:', err);
      setError('Failed to load partner overview');
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
      const response = await axios.get('/api/partners', { params });
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
      const response = await axios.get('/api/filters');
      setFilters(response.data);
    } catch (err) {
      console.error('Error fetching filters:', err);
    }
  };

  const fetchTierAnalytics = async () => {
    try {
      // Add cache busting parameter to ensure fresh data
      const cacheBuster = `?t=${Date.now()}`;
      const response = await axios.get(`/api/tier-analytics${cacheBuster}`);
      setTierAnalytics(response.data);
    } catch (err) {
      console.error('Error fetching tier analytics:', err);
    }
  };

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

  const handleReset = () => {
    // Reset all filters and sorting to default state
    setActiveFilters({});
    setSortField('total_earnings');
    setSortDirection('desc');
    setCurrentPage(1);
    // Fetch partners with default settings
    fetchPartners({}, 1);
  };

  const handlePartnerSelect = (partner) => {
    // Capture current state before navigation
    const currentScrollPosition = window.pageYOffset || document.documentElement.scrollTop;
    const currentState = {
      scrollPosition: currentScrollPosition,
      savedFilters: activeFilters,
      savedPage: currentPage,
      savedSortField: sortField,
      savedSortDirection: sortDirection
    };
    
    navigate(`/partner/${partner.partner_id}`, { state: currentState });
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
      
      if (rounded >= 1000000) {
        return `${(rounded / 1000000).toFixed(1)}M`;
      } else if (rounded >= 1000) {
        return `${(rounded / 1000).toFixed(1)}K`;
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

  // Show main loading screen during initial data fetch
  if (loading && (!overview || !tierAnalytics || partners.length === 0)) {
    return <LoadingScreen fullscreen />;
  }

  return (
    <div className="app-container">
      {/* Header */}
      <header className="header">
        <div className="header-content">
          <div className="header-left">
            <img src="/Deriv.png" alt="Deriv" className="logo" />
            <h1 className="heading-lg">Partner Dashboard</h1>
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
              onReset={handleReset}
              formatCurrency={formatCurrency}
              formatNumber={formatNumber}
              formatVolume={formatVolume}
              getTierColor={getTierColor}
              sortField={sortField}
              sortDirection={sortDirection}
              onSortChange={handleSortChange}
              // Pagination props
              currentPage={currentPage}
              totalPages={totalPages}
              totalCount={totalCount}
              partnersPerPage={partnersPerPage}
              onPageChange={handlePageChange}
            />
          } />
          <Route path="/partner/:partnerId" element={
            <PartnerDetailPage
              formatCurrency={formatCurrency}
              formatNumber={formatNumber}
              formatVolume={formatVolume}
              getTierColor={getTierColor}
            />
          } />
        </Routes>
      </main>
    </div>
  );
}

export default App; 