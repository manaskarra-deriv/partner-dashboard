import React, { useState } from 'react';
import PartnerOverview from './PartnerOverview';
import PerformanceAnalytics from './PerformanceAnalytics';
import TierAnalytics from './TierAnalytics';
import ApplicationFunnel from './ApplicationFunnel';
import PartnerTable from './PartnerTable';
import PartnerFilters from './PartnerFilters';
import AICopilot from './AICopilot';

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
  availableRegions,
  activeTab,
  setActiveTab,
  // New separate loading states and data
  performanceAnalyticsLoading,
  tierAnalyticsLoading,
  performanceAnalyticsData,
  tierAnalyticsData
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
            Application Funnel
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
              />
            </section>
          )}

          {/* Performance Analytics Section */}
          <section className="performance-analytics-section">
            <PerformanceAnalytics 
              analytics={performanceAnalyticsData}
              formatCurrency={formatCurrency}
              formatNumber={formatNumber}
              formatVolume={formatVolume}
              mainLoading={performanceAnalyticsLoading}
            />
          </section>

          {/* Tier Analytics Section */}
          <section className="tier-analytics-section">
            <TierAnalytics 
              analytics={tierAnalyticsData}
              formatCurrency={formatCurrency}
              formatNumber={formatNumber}
              formatVolume={formatVolume}
              mainLoading={tierAnalyticsLoading}
            />
          </section>
        </div>

        {/* Application Funnel Tab */}
        <div className={`tab-content ${activeTab === 'funnel' ? 'active' : ''}`}>
          <section className="application-funnel-section">
            <ApplicationFunnel 
              formatNumber={formatNumber}
              getTierColor={getTierColor}
              mainLoading={loading}
              funnelData={funnelData}
              availableCountries={availableCountries}
              availableRegions={availableRegions}
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
              />
            </div>
          </section>
        </div>
      </div>

      {/* AI Copilot for Dashboard Insights - Always visible */}
      <AICopilot 
        context="dashboard"
        data={{
          overview,
          partners: partners.slice(0, 10), // Top 10 partners for analysis
          activeFilters
        }}
      />
    </div>
  );
};

export default Dashboard; 