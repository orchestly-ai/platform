/**
 * White-Label / Reseller Page - Enterprise Branding Management
 *
 * Allows enterprise customers and resellers to:
 * - Configure custom branding (logo, colors, domain)
 * - Manage partner/reseller accounts
 * - Track customer attribution and commissions
 *
 * Backend: /api/v1/partners, /api/v1/branding/*
 */

import { useState, useEffect } from 'react';
import {
  Palette,
  Plus,
  Trash2,
  CheckCircle,
  AlertTriangle,
  X,
  Loader2,
  Globe,
  Image,
  Type,
  Eye,
  Building2,
  Users,
  DollarSign,
  TrendingUp,
  Copy,
  Edit,
  ExternalLink,
  Key,
  RefreshCw,
} from 'lucide-react';

interface Partner {
  id: number;
  partner_code: string;
  company_name: string;
  contact_email: string;
  tier: 'startup' | 'growth' | 'enterprise';
  status: 'pending' | 'active' | 'suspended';
  commission_rate: number;
  referral_code: string;
  total_revenue: number;
  total_commission: number;
  created_at: string;
}

interface Branding {
  id: number;
  partner_id: number;
  custom_domain: string;
  company_name: string;
  logo_url?: string;
  favicon_url?: string;
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  email_from_name?: string;
  email_from_address?: string;
  support_email?: string;
  support_url?: string;
  is_active: boolean;
  created_at: string;
}

interface Customer {
  id: number;
  partner_id: number;
  organization_id: string;
  organization_name: string;
  mrr: number;
  signup_source: string;
  is_active: boolean;
  created_at: string;
}

interface PartnerStats {
  total_customers: number;
  active_customers: number;
  churned_customers: number;
  total_revenue: number;
  pending_commission: number;
  paid_commission: number;
  retention_rate: number;
}

const API_BASE = 'http://localhost:8000';

export function WhiteLabelPage() {
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'branding' | 'customers' | 'commissions'>('branding');
  const [partners, setPartners] = useState<Partner[]>([]);
  const [selectedPartner, setSelectedPartner] = useState<Partner | null>(null);
  const [branding, setBranding] = useState<Branding | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [stats, setStats] = useState<PartnerStats | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Modal states
  const [showPartnerModal, setShowPartnerModal] = useState(false);
  const [showBrandingModal, setShowBrandingModal] = useState(false);
  const [saving, setSaving] = useState(false);

  // Form states
  const [partnerForm, setPartnerForm] = useState({
    company_name: '',
    contact_email: '',
    contact_name: '',
    tier: 'startup' as const,
    commission_rate: 20,
  });

  const [brandingForm, setBrandingForm] = useState({
    custom_domain: '',
    company_name: '',
    logo_url: '',
    favicon_url: '',
    primary_color: '#6366f1',
    secondary_color: '#4f46e5',
    accent_color: '#818cf8',
    email_from_name: '',
    email_from_address: '',
    support_email: '',
    support_url: '',
  });

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  useEffect(() => {
    fetchPartners();
  }, []);

  useEffect(() => {
    if (selectedPartner) {
      fetchPartnerDetails(selectedPartner.id);
    }
  }, [selectedPartner]);

  const fetchPartners = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/partners`);
      if (response.ok) {
        const data = await response.json();
        setPartners(data);
        if (data.length > 0 && !selectedPartner) {
          setSelectedPartner(data[0]);
        }
      }
    } catch (error) {
      console.error('Error fetching partners:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchPartnerDetails = async (partnerId: number) => {
    try {
      const [brandingRes, customersRes, statsRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/partners/${partnerId}/branding`),
        fetch(`${API_BASE}/api/v1/partners/${partnerId}/customers`),
        fetch(`${API_BASE}/api/v1/partners/${partnerId}/stats`),
      ]);

      if (brandingRes.ok) {
        const brandingData = await brandingRes.json();
        setBranding(brandingData[0] || null);
      }

      if (customersRes.ok) {
        const customersData = await customersRes.json();
        setCustomers(customersData);
      }

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }
    } catch (error) {
      console.error('Error fetching partner details:', error);
    }
  };

  const createPartner = async () => {
    if (!partnerForm.company_name || !partnerForm.contact_email) {
      setToast({ message: 'Company name and email are required', type: 'error' });
      return;
    }

    setSaving(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/partners`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(partnerForm),
      });

      if (response.ok) {
        const data = await response.json();
        setToast({ message: 'Partner created successfully', type: 'success' });
        setShowPartnerModal(false);
        fetchPartners();
        setSelectedPartner(data);
      } else {
        const error = await response.json();
        setToast({ message: error.detail || 'Failed to create partner', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to create partner', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const saveBranding = async () => {
    if (!selectedPartner) return;

    if (!brandingForm.custom_domain || !brandingForm.company_name) {
      setToast({ message: 'Domain and company name are required', type: 'error' });
      return;
    }

    setSaving(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/partners/${selectedPartner.id}/branding`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(brandingForm),
      });

      if (response.ok) {
        setToast({ message: 'Branding saved successfully', type: 'success' });
        setShowBrandingModal(false);
        fetchPartnerDetails(selectedPartner.id);
      } else {
        const error = await response.json();
        setToast({ message: error.detail || 'Failed to save branding', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to save branding', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setToast({ message: 'Copied to clipboard', type: 'success' });
  };

  const openBrandingModal = () => {
    if (branding) {
      setBrandingForm({
        custom_domain: branding.custom_domain || '',
        company_name: branding.company_name || '',
        logo_url: branding.logo_url || '',
        favicon_url: branding.favicon_url || '',
        primary_color: branding.primary_color || '#6366f1',
        secondary_color: branding.secondary_color || '#4f46e5',
        accent_color: branding.accent_color || '#818cf8',
        email_from_name: branding.email_from_name || '',
        email_from_address: branding.email_from_address || '',
        support_email: branding.support_email || '',
        support_url: branding.support_url || '',
      });
    } else {
      setBrandingForm({
        custom_domain: '',
        company_name: selectedPartner?.company_name || '',
        logo_url: '',
        favicon_url: '',
        primary_color: '#6366f1',
        secondary_color: '#4f46e5',
        accent_color: '#818cf8',
        email_from_name: '',
        email_from_address: '',
        support_email: '',
        support_url: '',
      });
    }
    setShowBrandingModal(true);
  };

  const getTierColor = (tier: string) => {
    switch (tier) {
      case 'enterprise': return 'bg-purple-100 text-purple-800';
      case 'growth': return 'bg-blue-100 text-blue-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800';
      case 'suspended': return 'bg-red-100 text-red-800';
      default: return 'bg-yellow-100 text-yellow-800';
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Toast */}
      {toast && (
        <div className={`fixed bottom-4 right-4 px-4 py-2 rounded-lg shadow-lg ${
          toast.type === 'success' ? 'bg-green-500' : 'bg-red-500'
        } text-white z-50 flex items-center gap-2`}>
          {toast.type === 'success' ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
          {toast.message}
        </div>
      )}

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
              <Palette className="w-8 h-8 text-pink-600" />
              White-Label & Reseller
              <span className="text-sm font-normal text-pink-600 bg-pink-100 px-2 py-1 rounded">Enterprise</span>
            </h1>
            <p className="text-gray-600 mt-1">
              Configure custom branding, manage partners, and track commissions
            </p>
          </div>
          <button
            onClick={() => setShowPartnerModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-pink-600 text-white rounded-lg hover:bg-pink-700"
          >
            <Plus className="w-4 h-4" />
            Add Partner
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center p-12">
          <Loader2 className="w-8 h-8 animate-spin text-pink-600" />
        </div>
      ) : partners.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <Building2 className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">No Partners Yet</h2>
          <p className="text-gray-600 mb-4">Create your first partner account to start white-labeling</p>
          <button
            onClick={() => setShowPartnerModal(true)}
            className="px-4 py-2 bg-pink-600 text-white rounded-lg hover:bg-pink-700"
          >
            Create Partner Account
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-6">
          {/* Partner List */}
          <div className="col-span-1">
            <div className="bg-white rounded-lg shadow">
              <div className="p-4 border-b">
                <h2 className="font-semibold">Partners</h2>
              </div>
              <div className="divide-y max-h-[600px] overflow-y-auto">
                {partners.map((partner) => (
                  <button
                    key={partner.id}
                    onClick={() => setSelectedPartner(partner)}
                    className={`w-full p-4 text-left hover:bg-gray-50 ${
                      selectedPartner?.id === partner.id ? 'bg-pink-50 border-l-4 border-pink-600' : ''
                    }`}
                  >
                    <div className="font-medium">{partner.company_name}</div>
                    <div className="text-sm text-gray-500">{partner.partner_code}</div>
                    <div className="flex items-center gap-2 mt-2">
                      <span className={`text-xs px-2 py-0.5 rounded ${getTierColor(partner.tier)}`}>
                        {partner.tier}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded ${getStatusColor(partner.status)}`}>
                        {partner.status}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Partner Details */}
          <div className="col-span-3">
            {selectedPartner && (
              <div className="space-y-6">
                {/* Partner Info Card */}
                <div className="bg-white rounded-lg shadow p-6">
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-4">
                      <div className="w-14 h-14 bg-pink-100 rounded-lg flex items-center justify-center">
                        <Building2 className="w-7 h-7 text-pink-600" />
                      </div>
                      <div>
                        <h2 className="text-xl font-semibold">{selectedPartner.company_name}</h2>
                        <p className="text-sm text-gray-500">{selectedPartner.contact_email}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`px-3 py-1 rounded-full text-sm ${getTierColor(selectedPartner.tier)}`}>
                        {selectedPartner.tier}
                      </span>
                      <span className={`px-3 py-1 rounded-full text-sm ${getStatusColor(selectedPartner.status)}`}>
                        {selectedPartner.status}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-4">
                    <div className="bg-gray-50 p-4 rounded-lg">
                      <div className="flex items-center gap-2 mb-1">
                        <Key className="w-4 h-4 text-gray-500" />
                        <span className="text-sm text-gray-500">Partner Code</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <code className="font-mono font-medium">{selectedPartner.partner_code}</code>
                        <button onClick={() => copyToClipboard(selectedPartner.partner_code)} className="text-gray-400 hover:text-gray-600">
                          <Copy className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                    <div className="bg-gray-50 p-4 rounded-lg">
                      <div className="flex items-center gap-2 mb-1">
                        <ExternalLink className="w-4 h-4 text-gray-500" />
                        <span className="text-sm text-gray-500">Referral Code</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <code className="font-mono font-medium">{selectedPartner.referral_code}</code>
                        <button onClick={() => copyToClipboard(selectedPartner.referral_code)} className="text-gray-400 hover:text-gray-600">
                          <Copy className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                    <div className="bg-gray-50 p-4 rounded-lg">
                      <div className="flex items-center gap-2 mb-1">
                        <DollarSign className="w-4 h-4 text-gray-500" />
                        <span className="text-sm text-gray-500">Commission Rate</span>
                      </div>
                      <div className="font-medium">{selectedPartner.commission_rate}%</div>
                    </div>
                  </div>
                </div>

                {/* Stats Cards */}
                {stats && (
                  <div className="grid grid-cols-4 gap-4">
                    <div className="bg-white rounded-lg shadow p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm text-gray-500">Customers</p>
                          <p className="text-2xl font-bold">{stats.active_customers}</p>
                        </div>
                        <Users className="w-8 h-8 text-blue-500" />
                      </div>
                      <p className="text-xs text-gray-500 mt-2">{stats.total_customers} total</p>
                    </div>
                    <div className="bg-white rounded-lg shadow p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm text-gray-500">Total Revenue</p>
                          <p className="text-2xl font-bold">${stats.total_revenue.toLocaleString()}</p>
                        </div>
                        <DollarSign className="w-8 h-8 text-green-500" />
                      </div>
                    </div>
                    <div className="bg-white rounded-lg shadow p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm text-gray-500">Pending Commission</p>
                          <p className="text-2xl font-bold">${stats.pending_commission.toLocaleString()}</p>
                        </div>
                        <TrendingUp className="w-8 h-8 text-amber-500" />
                      </div>
                    </div>
                    <div className="bg-white rounded-lg shadow p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm text-gray-500">Retention Rate</p>
                          <p className="text-2xl font-bold">{stats.retention_rate.toFixed(1)}%</p>
                        </div>
                        <CheckCircle className="w-8 h-8 text-purple-500" />
                      </div>
                    </div>
                  </div>
                )}

                {/* Tabs */}
                <div className="bg-white rounded-lg shadow">
                  <div className="border-b flex">
                    <button
                      onClick={() => setActiveTab('branding')}
                      className={`px-6 py-3 font-medium ${
                        activeTab === 'branding'
                          ? 'text-pink-600 border-b-2 border-pink-600'
                          : 'text-gray-500 hover:text-gray-700'
                      }`}
                    >
                      <Palette className="w-4 h-4 inline mr-2" />
                      Branding
                    </button>
                    <button
                      onClick={() => setActiveTab('customers')}
                      className={`px-6 py-3 font-medium ${
                        activeTab === 'customers'
                          ? 'text-pink-600 border-b-2 border-pink-600'
                          : 'text-gray-500 hover:text-gray-700'
                      }`}
                    >
                      <Users className="w-4 h-4 inline mr-2" />
                      Customers
                    </button>
                    <button
                      onClick={() => setActiveTab('commissions')}
                      className={`px-6 py-3 font-medium ${
                        activeTab === 'commissions'
                          ? 'text-pink-600 border-b-2 border-pink-600'
                          : 'text-gray-500 hover:text-gray-700'
                      }`}
                    >
                      <DollarSign className="w-4 h-4 inline mr-2" />
                      Commissions
                    </button>
                  </div>

                  <div className="p-6">
                    {activeTab === 'branding' && (
                      <div>
                        {branding ? (
                          <div className="space-y-6">
                            <div className="flex items-center justify-between">
                              <h3 className="font-semibold">Current Branding</h3>
                              <button
                                onClick={openBrandingModal}
                                className="flex items-center gap-2 text-pink-600 hover:text-pink-700"
                              >
                                <Edit className="w-4 h-4" />
                                Edit
                              </button>
                            </div>

                            <div className="grid grid-cols-2 gap-6">
                              <div>
                                <label className="text-sm font-medium text-gray-500">Custom Domain</label>
                                <div className="flex items-center gap-2 mt-1">
                                  <Globe className="w-4 h-4 text-gray-400" />
                                  <span className="font-medium">{branding.custom_domain}</span>
                                  {branding.is_active && (
                                    <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded">Active</span>
                                  )}
                                </div>
                              </div>
                              <div>
                                <label className="text-sm font-medium text-gray-500">Company Name</label>
                                <p className="mt-1 font-medium">{branding.company_name}</p>
                              </div>
                            </div>

                            <div>
                              <label className="text-sm font-medium text-gray-500">Colors</label>
                              <div className="flex items-center gap-4 mt-2">
                                <div className="flex items-center gap-2">
                                  <div className="w-8 h-8 rounded" style={{ backgroundColor: branding.primary_color }} />
                                  <span className="text-sm">Primary</span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <div className="w-8 h-8 rounded" style={{ backgroundColor: branding.secondary_color }} />
                                  <span className="text-sm">Secondary</span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <div className="w-8 h-8 rounded" style={{ backgroundColor: branding.accent_color }} />
                                  <span className="text-sm">Accent</span>
                                </div>
                              </div>
                            </div>

                            {branding.logo_url && (
                              <div>
                                <label className="text-sm font-medium text-gray-500">Logo</label>
                                <div className="mt-2 p-4 bg-gray-50 rounded-lg inline-block">
                                  <img src={branding.logo_url} alt="Logo" className="h-12" />
                                </div>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="text-center py-8">
                            <Palette className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                            <p className="text-gray-600 mb-4">No branding configured</p>
                            <button
                              onClick={openBrandingModal}
                              className="px-4 py-2 bg-pink-600 text-white rounded-lg hover:bg-pink-700"
                            >
                              Configure Branding
                            </button>
                          </div>
                        )}
                      </div>
                    )}

                    {activeTab === 'customers' && (
                      <div>
                        {customers.length === 0 ? (
                          <div className="text-center py-8">
                            <Users className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                            <p className="text-gray-600">No customers yet</p>
                          </div>
                        ) : (
                          <table className="w-full">
                            <thead>
                              <tr className="text-left text-sm text-gray-500 border-b">
                                <th className="pb-3">Organization</th>
                                <th className="pb-3">MRR</th>
                                <th className="pb-3">Source</th>
                                <th className="pb-3">Status</th>
                                <th className="pb-3">Joined</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y">
                              {customers.map((customer) => (
                                <tr key={customer.id} className="hover:bg-gray-50">
                                  <td className="py-3">
                                    <div className="font-medium">{customer.organization_name}</div>
                                    <div className="text-sm text-gray-500">{customer.organization_id}</div>
                                  </td>
                                  <td className="py-3">${customer.mrr.toLocaleString()}</td>
                                  <td className="py-3">{customer.signup_source}</td>
                                  <td className="py-3">
                                    <span className={`text-xs px-2 py-1 rounded ${
                                      customer.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                                    }`}>
                                      {customer.is_active ? 'Active' : 'Churned'}
                                    </span>
                                  </td>
                                  <td className="py-3 text-sm text-gray-500">
                                    {new Date(customer.created_at).toLocaleDateString()}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </div>
                    )}

                    {activeTab === 'commissions' && (
                      <div className="text-center py-8">
                        <DollarSign className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                        <p className="text-gray-600 mb-2">Commission Management</p>
                        <p className="text-sm text-gray-500">View and manage commission payments</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Create Partner Modal */}
      {showPartnerModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
            <div className="p-4 border-b flex items-center justify-between">
              <h2 className="text-lg font-semibold">Create Partner Account</h2>
              <button onClick={() => setShowPartnerModal(false)} className="text-gray-500 hover:text-gray-700">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Company Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={partnerForm.company_name}
                  onChange={(e) => setPartnerForm({ ...partnerForm, company_name: e.target.value })}
                  placeholder="Acme Inc."
                  className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-pink-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Contact Email <span className="text-red-500">*</span>
                </label>
                <input
                  type="email"
                  value={partnerForm.contact_email}
                  onChange={(e) => setPartnerForm({ ...partnerForm, contact_email: e.target.value })}
                  placeholder="partner@example.com"
                  className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-pink-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Contact Name</label>
                <input
                  type="text"
                  value={partnerForm.contact_name}
                  onChange={(e) => setPartnerForm({ ...partnerForm, contact_name: e.target.value })}
                  placeholder="John Doe"
                  className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-pink-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Partner Tier</label>
                  <select
                    value={partnerForm.tier}
                    onChange={(e) => setPartnerForm({ ...partnerForm, tier: e.target.value as any })}
                    className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-pink-500"
                  >
                    <option value="startup">Startup</option>
                    <option value="growth">Growth</option>
                    <option value="enterprise">Enterprise</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Commission Rate (%)</label>
                  <input
                    type="number"
                    value={partnerForm.commission_rate}
                    onChange={(e) => setPartnerForm({ ...partnerForm, commission_rate: parseInt(e.target.value) || 0 })}
                    min={0}
                    max={50}
                    className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-pink-500"
                  />
                </div>
              </div>
            </div>

            <div className="p-4 border-t bg-gray-50 flex justify-end gap-3">
              <button
                onClick={() => setShowPartnerModal(false)}
                className="px-4 py-2 border rounded-lg hover:bg-gray-100"
              >
                Cancel
              </button>
              <button
                onClick={createPartner}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2 bg-pink-600 text-white rounded-lg hover:bg-pink-700 disabled:opacity-50"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                Create Partner
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Branding Modal */}
      {showBrandingModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-4 border-b flex items-center justify-between sticky top-0 bg-white">
              <h2 className="text-lg font-semibold">Configure Branding</h2>
              <button onClick={() => setShowBrandingModal(false)} className="text-gray-500 hover:text-gray-700">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Domain & Name */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    <Globe className="w-4 h-4 inline mr-1" />
                    Custom Domain <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={brandingForm.custom_domain}
                    onChange={(e) => setBrandingForm({ ...brandingForm, custom_domain: e.target.value })}
                    placeholder="agents.yourcompany.com"
                    className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-pink-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    <Type className="w-4 h-4 inline mr-1" />
                    Company Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={brandingForm.company_name}
                    onChange={(e) => setBrandingForm({ ...brandingForm, company_name: e.target.value })}
                    placeholder="Your Company"
                    className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-pink-500"
                  />
                </div>
              </div>

              {/* Colors */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Brand Colors</label>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="text-xs text-gray-500">Primary</label>
                    <div className="flex items-center gap-2 mt-1">
                      <input
                        type="color"
                        value={brandingForm.primary_color}
                        onChange={(e) => setBrandingForm({ ...brandingForm, primary_color: e.target.value })}
                        className="w-10 h-10 rounded border cursor-pointer"
                      />
                      <input
                        type="text"
                        value={brandingForm.primary_color}
                        onChange={(e) => setBrandingForm({ ...brandingForm, primary_color: e.target.value })}
                        className="flex-1 border rounded px-2 py-1 text-sm font-mono"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-gray-500">Secondary</label>
                    <div className="flex items-center gap-2 mt-1">
                      <input
                        type="color"
                        value={brandingForm.secondary_color}
                        onChange={(e) => setBrandingForm({ ...brandingForm, secondary_color: e.target.value })}
                        className="w-10 h-10 rounded border cursor-pointer"
                      />
                      <input
                        type="text"
                        value={brandingForm.secondary_color}
                        onChange={(e) => setBrandingForm({ ...brandingForm, secondary_color: e.target.value })}
                        className="flex-1 border rounded px-2 py-1 text-sm font-mono"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-gray-500">Accent</label>
                    <div className="flex items-center gap-2 mt-1">
                      <input
                        type="color"
                        value={brandingForm.accent_color}
                        onChange={(e) => setBrandingForm({ ...brandingForm, accent_color: e.target.value })}
                        className="w-10 h-10 rounded border cursor-pointer"
                      />
                      <input
                        type="text"
                        value={brandingForm.accent_color}
                        onChange={(e) => setBrandingForm({ ...brandingForm, accent_color: e.target.value })}
                        className="flex-1 border rounded px-2 py-1 text-sm font-mono"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Logos */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    <Image className="w-4 h-4 inline mr-1" />
                    Logo URL
                  </label>
                  <input
                    type="text"
                    value={brandingForm.logo_url}
                    onChange={(e) => setBrandingForm({ ...brandingForm, logo_url: e.target.value })}
                    placeholder="https://yourcdn.com/logo.png"
                    className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-pink-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Favicon URL</label>
                  <input
                    type="text"
                    value={brandingForm.favicon_url}
                    onChange={(e) => setBrandingForm({ ...brandingForm, favicon_url: e.target.value })}
                    placeholder="https://yourcdn.com/favicon.ico"
                    className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-pink-500"
                  />
                </div>
              </div>

              {/* Email Settings */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Email Settings</label>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-gray-500">From Name</label>
                    <input
                      type="text"
                      value={brandingForm.email_from_name}
                      onChange={(e) => setBrandingForm({ ...brandingForm, email_from_name: e.target.value })}
                      placeholder="Your Company"
                      className="w-full border rounded-lg px-3 py-2 mt-1 focus:outline-none focus:ring-2 focus:ring-pink-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500">From Address</label>
                    <input
                      type="email"
                      value={brandingForm.email_from_address}
                      onChange={(e) => setBrandingForm({ ...brandingForm, email_from_address: e.target.value })}
                      placeholder="noreply@yourcompany.com"
                      className="w-full border rounded-lg px-3 py-2 mt-1 focus:outline-none focus:ring-2 focus:ring-pink-500"
                    />
                  </div>
                </div>
              </div>

              {/* Support Settings */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Support Email</label>
                  <input
                    type="email"
                    value={brandingForm.support_email}
                    onChange={(e) => setBrandingForm({ ...brandingForm, support_email: e.target.value })}
                    placeholder="support@yourcompany.com"
                    className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-pink-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Support URL</label>
                  <input
                    type="text"
                    value={brandingForm.support_url}
                    onChange={(e) => setBrandingForm({ ...brandingForm, support_url: e.target.value })}
                    placeholder="https://help.yourcompany.com"
                    className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-pink-500"
                  />
                </div>
              </div>

              {/* Preview */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Preview</label>
                <div className="border rounded-lg p-4" style={{ borderColor: brandingForm.primary_color }}>
                  <div className="flex items-center gap-3 mb-4">
                    {brandingForm.logo_url ? (
                      <img src={brandingForm.logo_url} alt="Logo" className="h-8" />
                    ) : (
                      <div className="w-8 h-8 rounded" style={{ backgroundColor: brandingForm.primary_color }} />
                    )}
                    <span className="font-bold" style={{ color: brandingForm.primary_color }}>
                      {brandingForm.company_name || 'Your Company'}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <button className="px-4 py-2 rounded text-white" style={{ backgroundColor: brandingForm.primary_color }}>
                      Primary Button
                    </button>
                    <button className="px-4 py-2 rounded text-white" style={{ backgroundColor: brandingForm.secondary_color }}>
                      Secondary
                    </button>
                    <button className="px-4 py-2 rounded border" style={{ borderColor: brandingForm.accent_color, color: brandingForm.accent_color }}>
                      Accent
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div className="p-4 border-t bg-gray-50 flex justify-end gap-3 sticky bottom-0">
              <button
                onClick={() => setShowBrandingModal(false)}
                className="px-4 py-2 border rounded-lg hover:bg-gray-100"
              >
                Cancel
              </button>
              <button
                onClick={saveBranding}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2 bg-pink-600 text-white rounded-lg hover:bg-pink-700 disabled:opacity-50"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                Save Branding
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default WhiteLabelPage;
