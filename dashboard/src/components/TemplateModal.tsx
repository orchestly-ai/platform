/**
 * Template Modal Component
 * Displays workflow and agent templates for quick start
 */

import { useState } from 'react';
import { X, Search, Sparkles, Bot, GitBranch, ArrowRight } from 'lucide-react';
import type { WorkflowTemplate, TemplateCategory } from '../data/workflowTemplates';
import { getTemplatesByCategory } from '../data/workflowTemplates';

interface TemplateModalProps {
  isOpen: boolean;
  category: TemplateCategory;
  onClose: () => void;
  onSelectTemplate: (template: WorkflowTemplate) => void;
}

export function TemplateModal({ isOpen, category, onClose, onSelectTemplate }: TemplateModalProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState<WorkflowTemplate | null>(null);

  if (!isOpen) return null;

  const templates = getTemplatesByCategory(category);
  const filteredTemplates = templates.filter(template =>
    template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    template.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
    template.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const handleUseTemplate = (template: WorkflowTemplate) => {
    onSelectTemplate(template);
    onClose();
  };

  const categoryLabel = category === 'agent' ? 'Agent' : 'Workflow';
  const categoryIcon = category === 'agent' ? Bot : GitBranch;
  const CategoryIcon = categoryIcon;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        backdropFilter: 'blur(4px)',
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: 'var(--bg-primary)',
          borderRadius: '16px',
          width: '90%',
          maxWidth: '1200px',
          maxHeight: '90vh',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 24px 48px rgba(0, 0, 0, 0.3)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '24px 32px',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                background: category === 'agent' ? 'rgba(99, 102, 241, 0.1)' : 'rgba(34, 197, 94, 0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <CategoryIcon size={24} style={{ color: category === 'agent' ? '#6366f1' : '#22c55e' }} />
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)' }}>
                {categoryLabel} Templates
              </h2>
              <p style={{ margin: '4px 0 0', fontSize: '14px', color: 'var(--text-muted)' }}>
                Choose a template to get started quickly
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              padding: '8px',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-muted)',
            }}
          >
            <X size={24} />
          </button>
        </div>

        {/* Search */}
        <div style={{ padding: '20px 32px', borderBottom: '1px solid var(--border-color)' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              borderRadius: '10px',
              padding: '12px 16px',
            }}
          >
            <Search size={20} style={{ color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder={`Search ${categoryLabel.toLowerCase()} templates...`}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                flex: 1,
                border: 'none',
                background: 'transparent',
                outline: 'none',
                fontSize: '15px',
                color: 'var(--text-primary)',
              }}
            />
          </div>
        </div>

        {/* Templates Grid */}
        <div style={{ flex: 1, overflow: 'auto', padding: '24px 32px' }}>
          {filteredTemplates.length === 0 ? (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '60px 20px',
                color: 'var(--text-muted)',
              }}
            >
              <Search size={48} style={{ marginBottom: '16px', opacity: 0.3 }} />
              <p style={{ fontSize: '16px', margin: 0 }}>No templates found</p>
              <p style={{ fontSize: '14px', margin: '8px 0 0' }}>Try a different search term</p>
            </div>
          ) : (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
                gap: '16px',
              }}
            >
              {filteredTemplates.map((template) => (
                <div
                  key={template.id}
                  className="chart-card"
                  style={{
                    padding: '20px',
                    cursor: 'pointer',
                    border: selectedTemplate?.id === template.id ? `2px solid ${template.color}` : '1px solid var(--border-color)',
                    transition: 'all 0.2s',
                    position: 'relative',
                    overflow: 'hidden',
                  }}
                  onClick={() => setSelectedTemplate(template)}
                  onDoubleClick={() => handleUseTemplate(template)}
                >
                  {/* Template Icon */}
                  <div
                    style={{
                      width: '56px',
                      height: '56px',
                      borderRadius: '14px',
                      background: `${template.color}15`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '28px',
                      marginBottom: '16px',
                    }}
                  >
                    {template.icon}
                  </div>

                  {/* Template Name */}
                  <h3 style={{ margin: '0 0 8px', fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {template.name}
                  </h3>

                  {/* Template Description */}
                  <p style={{ margin: '0 0 16px', fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.5' }}>
                    {template.description}
                  </p>

                  {/* Template Tags */}
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '16px' }}>
                    {template.tags.slice(0, 3).map((tag) => (
                      <span
                        key={tag}
                        style={{
                          fontSize: '11px',
                          padding: '4px 10px',
                          borderRadius: '6px',
                          background: 'var(--bg-secondary)',
                          color: 'var(--text-muted)',
                          textTransform: 'lowercase',
                        }}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>

                  {/* Template Stats */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      paddingTop: '12px',
                      borderTop: '1px solid var(--border-color)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-muted)' }}>
                      <Sparkles size={14} />
                      {template.nodes.length} node{template.nodes.length !== 1 ? 's' : ''}
                    </div>
                    {template.estimatedCost && (
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                        ~${template.estimatedCost.toFixed(2)}/run
                      </div>
                    )}
                  </div>

                  {/* Selected Indicator */}
                  {selectedTemplate?.id === template.id && (
                    <div
                      style={{
                        position: 'absolute',
                        top: '16px',
                        right: '16px',
                        width: '24px',
                        height: '24px',
                        borderRadius: '50%',
                        background: template.color,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'white',
                        fontSize: '14px',
                      }}
                    >
                      ✓
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '20px 32px',
            borderTop: '1px solid var(--border-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'var(--bg-secondary)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--text-muted)' }}>
            <span>💡 Tip: Double-click a template to use it instantly</span>
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button
              className="btn-primary"
              onClick={() => selectedTemplate && handleUseTemplate(selectedTemplate)}
              disabled={!selectedTemplate}
              style={{
                opacity: selectedTemplate ? 1 : 0.5,
                cursor: selectedTemplate ? 'pointer' : 'not-allowed',
              }}
            >
              Use Template
              <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default TemplateModal;
