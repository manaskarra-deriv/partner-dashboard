import React, { useState } from 'react';
import PartnerOverview from '../overview/PartnerOverview';
import PerformanceAnalytics from '../overview/PerformanceAnalytics';
import TierAnalytics from '../overview/TierAnalytics';
import CountryAnalysis from '../country-analysis/CountryAnalysis';
import PartnerTable from '../management/PartnerTable';
import PartnerFilters from '../management/PartnerFilters';

const Dashboard = ({ 
  overview, 
  tierAnalytics,
  partners, 
  filters, 
  activeFilters,
  loading, 
  onFilterChange, 
  onPartnerSelect,
  formatCurrency,
  formatNumber,
  formatVolume,
  getTierColor,
  sortField,
  sortDirection,
  onSortChange,
  showPII,
  onRequestPIIAccess,
  // Pagination props
  currentPage,
  totalPages,
  totalCount,
  partnersPerPage,
  onPageChange,
  funnelData,
  availableCountries,
  activeTab,
  setActiveTab,
  // New separate loading states and data
  performanceAnalyticsLoading,
  tierAnalyticsLoading,
  performanceAnalyticsData,
  tierAnalyticsData,
  // Partner navigation function
  navigateToPartnerDetail,
  // Global Partner Enablement preloaded data
  globalTierProgressionData,
  globalProgressionLoading,
  // CSV Export function
  onExportCSV,
  // Persistent country analysis state
  tierAnalyticsDataCountry,
  setTierAnalyticsDataCountry,
  monthlyCountryData,
  setMonthlyCountryData,
  tierProgressionData,
  setTierProgressionData,
  selectedCountry,
  setSelectedCountry,
  countryAnalysisLoading,
  setCountryAnalysisLoading
}) => {
  // Use activeTab and setActiveTab from props
  return (
    <div className="dashboard-container">
      {/* Main Navigation Tabs */}
      <div className="dashboard-header">
        <div className="dashboard-tabs">
          <button 
            className={`dashboard-tab ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            Partner Overview
          </button>
          <button 
            className={`dashboard-tab ${activeTab === 'funnel' ? 'active' : ''}`}
            onClick={() => setActiveTab('funnel')}
          >
            Country Analysis
          </button>
          <button 
            className={`dashboard-tab ${activeTab === 'management' ? 'active' : ''}`}
            onClick={() => setActiveTab('management')}
          >
            Partner Management
          </button>
        </div>
      </div>

      {/* Tab Content */}
      <div className="dashboard-content">
        {/* Overview Tab */}
        <div className={`tab-content ${activeTab === 'overview' ? 'active' : ''}`}>
          {/* Overview Section */}
          {overview && (
            <section className="overview-section">
              <div className="section-header">
                <h2 className="heading-lg">Partner Overview</h2>
                <p className="text-secondary">Real-time partner performance metrics</p>
              </div>
              <PartnerOverview 
                overview={overview} 
                formatCurrency={formatCurrency}
                formatNumber={formatNumber}
                formatVolume={formatVolume}
                performanceAnalyticsData={performanceAnalyticsData}
                tierAnalyticsData={tierAnalyticsData}
                performanceAnalyticsLoading={performanceAnalyticsLoading}
                tierAnalyticsLoading={tierAnalyticsLoading}
                navigateToPartnerDetail={navigateToPartnerDetail}
                // Preloaded global partner enablement data
                globalTierProgressionData={globalTierProgressionData}
                globalProgressionLoading={globalProgressionLoading}
              />
            </section>
          )}

          {/* Performance Analytics and Tier Analytics are now integrated into Partner Overview */}
        </div>

        {/* Country Analysis Tab */}
        <div className={`tab-content ${activeTab === 'funnel' ? 'active' : ''}`}>
          <section className="application-funnel-section">
            <CountryAnalysis 
              formatNumber={formatNumber}
              getTierColor={getTierColor}
              mainLoading={loading}
              funnelData={funnelData}
              availableCountries={availableCountries}
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
              countryAnalysisLoading={countryAnalysisLoading}
              setCountryAnalysisLoading={setCountryAnalysisLoading}
            />
          </section>
        </div>

        {/* Partner Management Tab */}
        <div className={`tab-content ${activeTab === 'management' ? 'active' : ''}`}>
          <section className="partners-section">
            <div className="section-header">
              <h2 className="heading-lg">Partner Management</h2>
              <p className="text-secondary">Filter and analyze partner performance</p>
            </div>

            <div className="filters-container">
              <PartnerFilters
                filters={filters}
                activeFilters={activeFilters}
                onFilterChange={onFilterChange}
              />
            </div>

            <div className="table-container">
              <PartnerTable
                partners={partners}
                loading={loading}
                onPartnerSelect={onPartnerSelect}
                formatCurrency={formatCurrency}
                formatNumber={formatNumber}
                formatVolume={formatVolume}
                getTierColor={getTierColor}
                sortField={sortField}
                sortDirection={sortDirection}
                onSortChange={onSortChange}
                activeFilters={activeFilters}
                showPII={showPII}
                onRequestPIIAccess={onRequestPIIAccess}
                // Pagination props
                currentPage={currentPage}
                totalPages={totalPages}
                totalCount={totalCount}
                partnersPerPage={partnersPerPage}
                onPageChange={onPageChange}
                mainLoading={loading}
                onExportCSV={onExportCSV}
              />
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

export default Dashboard; 