/**
 * PrintNode Component Tests
 *
 * Tests for the Print node visual component in the workflow builder.
 *
 * Test Coverage:
 * - Node rendering with different configurations
 * - Status color changes
 * - Label and message display
 * - Handle positions
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ReactFlowProvider } from 'reactflow'
import PrintNode from './PrintNode'

// Mock reactflow hooks
vi.mock('reactflow', async () => {
  const actual = await vi.importActual('reactflow')
  return {
    ...actual,
    Handle: ({ type, position }: { type: string; position: string }) => (
      <div data-testid={`handle-${type}-${position}`} />
    ),
  }
})

const defaultProps = {
  id: 'print-1',
  type: 'print',
  selected: false,
  data: {
    label: 'Test Print',
    type: 'print' as const,
    printConfig: {
      label: 'Debug Output',
      message: 'Hello World',
      logLevel: 'info' as const,
      includeTimestamp: true,
    },
  },
  xPos: 0,
  yPos: 0,
  isConnectable: true,
  zIndex: 0,
  dragging: false,
}

const renderPrintNode = (props = {}) => {
  return render(
    <ReactFlowProvider>
      <PrintNode {...defaultProps} {...props} />
    </ReactFlowProvider>
  )
}

describe('PrintNode', () => {
  describe('Basic Rendering', () => {
    it('renders the node with label', () => {
      renderPrintNode()

      expect(screen.getByText('Test Print')).toBeInTheDocument()
    })

    it('renders PRINT type indicator', () => {
      renderPrintNode()

      expect(screen.getByText('PRINT')).toBeInTheDocument()
    })

    it('renders print config label', () => {
      renderPrintNode()

      expect(screen.getByText('Label:')).toBeInTheDocument()
      expect(screen.getByText('Debug Output')).toBeInTheDocument()
    })

    it('renders message preview', () => {
      renderPrintNode()

      expect(screen.getByText('Hello World')).toBeInTheDocument()
    })

    it('renders input and output handles', () => {
      renderPrintNode()

      expect(screen.getByTestId('handle-target-top')).toBeInTheDocument()
      expect(screen.getByTestId('handle-source-bottom')).toBeInTheDocument()
    })
  })

  describe('Status Colors', () => {
    it('shows idle status by default', () => {
      const { container } = renderPrintNode({
        data: { ...defaultProps.data, status: 'idle' },
      })

      const node = container.querySelector('.bg-gray-200')
      expect(node).toBeInTheDocument()
    })

    it('shows running status with animation', () => {
      const { container } = renderPrintNode({
        data: { ...defaultProps.data, status: 'running' },
      })

      const node = container.querySelector('.animate-pulse')
      expect(node).toBeInTheDocument()
    })

    it('shows success status in green', () => {
      const { container } = renderPrintNode({
        data: { ...defaultProps.data, status: 'success' },
      })

      const node = container.querySelector('.bg-green-100')
      expect(node).toBeInTheDocument()
    })

    it('shows error status in red', () => {
      const { container } = renderPrintNode({
        data: { ...defaultProps.data, status: 'error' },
      })

      const node = container.querySelector('.bg-red-100')
      expect(node).toBeInTheDocument()
    })
  })

  describe('Selection State', () => {
    it('shows selection ring when selected', () => {
      const { container } = renderPrintNode({ selected: true })

      const node = container.querySelector('.ring-2')
      expect(node).toBeInTheDocument()
    })

    it('does not show selection ring when not selected', () => {
      const { container } = renderPrintNode({ selected: false })

      const node = container.querySelector('.ring-2')
      expect(node).not.toBeInTheDocument()
    })
  })

  describe('Empty/Default Configuration', () => {
    it('renders placeholder when no message configured', () => {
      renderPrintNode({
        data: {
          ...defaultProps.data,
          printConfig: {
            label: '',
            message: '',
            logLevel: 'info',
            includeTimestamp: true,
          },
        },
      })

      expect(screen.getByText('No message configured')).toBeInTheDocument()
    })

    it('uses default label when not configured', () => {
      renderPrintNode({
        data: {
          ...defaultProps.data,
          label: 'Print Output',
          printConfig: {},
        },
      })

      expect(screen.getByText('Print Output')).toBeInTheDocument()
    })
  })

  describe('Message Truncation', () => {
    it('truncates long messages', () => {
      const longMessage = 'A'.repeat(100)

      renderPrintNode({
        data: {
          ...defaultProps.data,
          printConfig: {
            ...defaultProps.data.printConfig,
            message: longMessage,
          },
        },
      })

      // Should show truncated message with ellipsis
      const truncated = screen.getByText(/^A+\.\.\.$/i)
      expect(truncated).toBeInTheDocument()
    })
  })

  describe('Execution Time Display', () => {
    it('shows execution time when available', () => {
      renderPrintNode({
        data: {
          ...defaultProps.data,
          executionTime: 150,
        },
      })

      expect(screen.getByText('150ms')).toBeInTheDocument()
    })

    it('does not show execution time when not available', () => {
      renderPrintNode()

      expect(screen.queryByText(/ms$/)).not.toBeInTheDocument()
    })
  })

  describe('Error Display', () => {
    it('shows error message when present', () => {
      renderPrintNode({
        data: {
          ...defaultProps.data,
          error: 'Something went wrong',
        },
      })

      expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    })

    it('does not show error section when no error', () => {
      renderPrintNode()

      expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument()
    })
  })
})
