import React, { useState, useRef, useEffect, useCallback } from 'react'
import { Node, Edge } from 'reactflow'
import { ChevronRight, Database, Zap, Bot, MessageSquare } from 'lucide-react'

interface VariablePickerProps {
  value: string
  onChange: (value: string) => void
  nodes: Node[]
  edges: Edge[]
  currentNodeId: string
  placeholder?: string
  rows?: number
  className?: string
}

interface VariableOption {
  nodeId: string
  nodeLabel: string
  nodeType: string
  field: string
  fieldLabel: string
  fullPath: string
  icon: React.ReactNode
}

// Define what outputs each node type produces
const NODE_OUTPUT_FIELDS: Record<string, { field: string; label: string }[]> = {
  trigger: [
    { field: 'ticket_id', label: 'Ticket ID' },
    { field: 'title', label: 'Title' },
    { field: 'description', label: 'Description' },
    { field: 'email', label: 'Email' },
    { field: 'user_id', label: 'User ID' },
    { field: 'data', label: 'Full Data' },
  ],
  supervisor: [
    { field: 'text', label: 'AI Response' },
    { field: 'model', label: 'Model Used' },
    { field: 'tokens', label: 'Token Usage' },
  ],
  worker: [
    { field: 'text', label: 'AI Response' },
    { field: 'model', label: 'Model Used' },
    { field: 'tokens', label: 'Token Usage' },
  ],
  integration: [
    { field: 'data', label: 'Response Data' },
    { field: 'success', label: 'Success Status' },
  ],
  condition: [
    { field: 'result', label: 'Condition Result' },
    { field: 'branch', label: 'Branch Taken' },
  ],
  tool: [
    { field: 'result', label: 'Tool Result' },
    { field: 'data', label: 'Response Data' },
  ],
}

// Get icon for node type
const getNodeIcon = (type: string) => {
  switch (type) {
    case 'trigger':
      return <Zap className="w-3 h-3 text-orange-500" />
    case 'supervisor':
    case 'worker':
      return <Bot className="w-3 h-3 text-blue-500" />
    case 'integration':
      return <MessageSquare className="w-3 h-3 text-green-500" />
    default:
      return <Database className="w-3 h-3 text-gray-500" />
  }
}

export const VariablePicker: React.FC<VariablePickerProps> = ({
  value,
  onChange,
  nodes,
  edges,
  currentNodeId,
  placeholder,
  rows = 4,
  className = '',
}) => {
  const [showPicker, setShowPicker] = useState(false)
  const [cursorPosition, setCursorPosition] = useState(0)
  const [searchFilter, setSearchFilter] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const pickerRef = useRef<HTMLDivElement>(null)

  // Compute upstream nodes (nodes that feed into current node)
  const getUpstreamNodes = useCallback((): Node[] => {
    const upstream: Set<string> = new Set()
    const visited: Set<string> = new Set()

    const traverse = (nodeId: string) => {
      if (visited.has(nodeId)) return
      visited.add(nodeId)

      edges.forEach(edge => {
        if (edge.target === nodeId) {
          upstream.add(edge.source)
          traverse(edge.source)
        }
      })
    }

    traverse(currentNodeId)

    return nodes.filter(n => upstream.has(n.id))
  }, [nodes, edges, currentNodeId])

  // Generate variable options
  const getVariableOptions = useCallback((): VariableOption[] => {
    const options: VariableOption[] = []

    // Always add input variables (from workflow execution input)
    const inputFields = [
      { field: 'ticket_id', label: 'Ticket ID' },
      { field: 'title', label: 'Title' },
      { field: 'description', label: 'Description' },
      { field: 'email', label: 'Email' },
      { field: 'user_id', label: 'User ID' },
      { field: 'data', label: 'Full Data' },
      { field: 'url', label: 'URL' },
      { field: 'message', label: 'Message' },
    ]

    inputFields.forEach(f => {
      options.push({
        nodeId: 'input',
        nodeLabel: 'Workflow Input',
        nodeType: 'input',
        field: f.field,
        fieldLabel: f.label,
        fullPath: `input.${f.field}`,
        icon: <Database className="w-3 h-3 text-purple-500" />,
      })
    })

    // Add upstream node outputs
    const upstreamNodes = getUpstreamNodes()
    upstreamNodes.forEach(node => {
      const nodeType = node.data?.type || node.type || 'unknown'
      const fields = NODE_OUTPUT_FIELDS[nodeType] || [{ field: 'data', label: 'Data' }]

      fields.forEach(f => {
        options.push({
          nodeId: node.id,
          nodeLabel: node.data?.label || node.id,
          nodeType,
          field: f.field,
          fieldLabel: f.label,
          fullPath: `${node.id}.${f.field}`,
          icon: getNodeIcon(nodeType),
        })
      })
    })

    return options
  }, [getUpstreamNodes])

  // Filter options based on search
  const filteredOptions = getVariableOptions().filter(opt => {
    if (!searchFilter) return true
    const search = searchFilter.toLowerCase()
    return (
      opt.nodeLabel.toLowerCase().includes(search) ||
      opt.field.toLowerCase().includes(search) ||
      opt.fieldLabel.toLowerCase().includes(search)
    )
  })

  // Group options by node
  const groupedOptions = filteredOptions.reduce((acc, opt) => {
    const key = opt.nodeId
    if (!acc[key]) {
      acc[key] = {
        nodeId: opt.nodeId,
        nodeLabel: opt.nodeLabel,
        nodeType: opt.nodeType,
        icon: opt.icon,
        fields: [],
      }
    }
    acc[key].fields.push(opt)
    return acc
  }, {} as Record<string, { nodeId: string; nodeLabel: string; nodeType: string; icon: React.ReactNode; fields: VariableOption[] }>)

  // Handle textarea changes
  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value
    const pos = e.target.selectionStart
    onChange(newValue)
    setCursorPosition(pos)

    // Check if user just typed {{
    const textBeforeCursor = newValue.slice(0, pos)
    const lastTwoChars = textBeforeCursor.slice(-2)

    if (lastTwoChars === '{{') {
      setShowPicker(true)
      setSearchFilter('')
      setSelectedIndex(0)
    } else if (showPicker) {
      // Update search filter based on what's typed after {{
      const match = textBeforeCursor.match(/\{\{([^}]*)$/)
      if (match) {
        setSearchFilter(match[1])
      } else {
        setShowPicker(false)
      }
    }
  }

  // Handle keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showPicker) return

    const flatOptions = Object.values(groupedOptions).flatMap(g => g.fields)

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setSelectedIndex(i => Math.min(i + 1, flatOptions.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setSelectedIndex(i => Math.max(i - 1, 0))
        break
      case 'Enter':
      case 'Tab':
        e.preventDefault()
        if (flatOptions[selectedIndex]) {
          insertVariable(flatOptions[selectedIndex])
        }
        break
      case 'Escape':
        setShowPicker(false)
        break
    }
  }

  // Insert selected variable
  const insertVariable = (option: VariableOption) => {
    if (!textareaRef.current) return

    const textarea = textareaRef.current
    const pos = textarea.selectionStart

    // Find the {{ before cursor
    const textBeforeCursor = value.slice(0, pos)
    const matchStart = textBeforeCursor.lastIndexOf('{{')

    if (matchStart === -1) return

    // Replace from {{ to cursor with the full variable
    const before = value.slice(0, matchStart)
    const after = value.slice(pos)
    const newValue = `${before}{{${option.fullPath}}}${after}`

    onChange(newValue)
    setShowPicker(false)

    // Set cursor position after the inserted variable
    setTimeout(() => {
      const newPos = matchStart + option.fullPath.length + 4 // +4 for {{ and }}
      textarea.setSelectionRange(newPos, newPos)
      textarea.focus()
    }, 0)
  }

  // Close picker when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        pickerRef.current &&
        !pickerRef.current.contains(e.target as HTMLElement) &&
        textareaRef.current &&
        !textareaRef.current.contains(e.target as HTMLElement)
      ) {
        setShowPicker(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div className="relative">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        rows={rows}
        className={`w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono text-sm ${className}`}
      />

      {/* Variable Picker Dropdown */}
      {showPicker && (
        <div
          ref={pickerRef}
          className="absolute z-50 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-64 overflow-y-auto"
        >
          <div className="p-2 border-b border-gray-100 bg-gray-50">
            <div className="text-xs text-gray-500 font-medium">
              Insert Variable {searchFilter && <span className="text-blue-500">"{searchFilter}"</span>}
            </div>
          </div>

          {Object.keys(groupedOptions).length === 0 ? (
            <div className="p-3 text-sm text-gray-500 text-center">
              No variables available
            </div>
          ) : (
            <div className="py-1">
              {Object.values(groupedOptions).map((group, groupIdx) => (
                <div key={group.nodeId}>
                  {/* Node header */}
                  <div className="px-3 py-1.5 bg-gray-50 flex items-center gap-2 text-xs font-medium text-gray-600 sticky top-0">
                    {group.icon}
                    <span>{group.nodeLabel}</span>
                    <span className="text-gray-400">({group.nodeId})</span>
                  </div>

                  {/* Fields */}
                  {group.fields.map((opt, fieldIdx) => {
                    const flatIdx = Object.values(groupedOptions)
                      .slice(0, groupIdx)
                      .reduce((acc, g) => acc + g.fields.length, 0) + fieldIdx
                    const isSelected = flatIdx === selectedIndex

                    return (
                      <button
                        key={opt.fullPath}
                        onClick={() => insertVariable(opt)}
                        className={`w-full px-3 py-2 text-left flex items-center gap-2 hover:bg-blue-50 ${
                          isSelected ? 'bg-blue-100' : ''
                        }`}
                      >
                        <ChevronRight className="w-3 h-3 text-gray-400" />
                        <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded text-blue-600">
                          {`{{${opt.fullPath}}}`}
                        </code>
                        <span className="text-xs text-gray-500 ml-auto">
                          {opt.fieldLabel}
                        </span>
                      </button>
                    )
                  })}
                </div>
              ))}
            </div>
          )}

          <div className="p-2 border-t border-gray-100 bg-gray-50 text-xs text-gray-400">
            ↑↓ Navigate • Enter Select • Esc Close
          </div>
        </div>
      )}

      <p className="text-xs text-gray-500 mt-1">
        Type <code className="bg-gray-100 px-1 rounded">{'{{'}</code> to insert variables from upstream nodes
      </p>
    </div>
  )
}

export default VariablePicker
