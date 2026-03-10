/**
 * Developers Page Tests
 *
 * Tests for the Developers page that shows integration guides
 * and API documentation with syntax-highlighted code blocks.
 *
 * Test Coverage:
 * - Page header and title
 * - Tab navigation (Quick Start, Python, JavaScript, REST API)
 * - Code blocks with syntax highlighting
 * - Copy-to-clipboard functionality
 * - Rebranded SDK references (orchestly, not agent-orchestrator)
 * - API links
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'

// Mock prism-react-renderer
vi.mock('prism-react-renderer', () => ({
  Highlight: ({ code, children }: { code: string; children: (props: any) => React.ReactNode }) =>
    children({
      style: {},
      tokens: [[{ content: code, types: ['plain'] }]],
      getLineProps: ({ key }: any) => ({ key }),
      getTokenProps: ({ key, token }: any) => ({ key, children: token.content }),
    }),
  themes: {
    oneDark: {},
  },
}))

import { DevelopersPage } from './Developers'

const renderDevelopers = () => {
  return render(
    <BrowserRouter>
      <DevelopersPage />
    </BrowserRouter>
  )
}

describe('DevelopersPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Mock clipboard API
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    })
  })

  describe('Page Header', () => {
    it('renders page title', () => {
      renderDevelopers()

      expect(screen.getByText('Developers')).toBeInTheDocument()
    })

    it('renders page description', () => {
      renderDevelopers()

      expect(
        screen.getByText('Integrate your applications with the Orchestly platform')
      ).toBeInTheDocument()
    })

    it('renders API Docs link', () => {
      renderDevelopers()

      expect(screen.getByText('API Docs')).toBeInTheDocument()
    })
  })

  describe('Tab Navigation', () => {
    it('renders all tab labels', () => {
      renderDevelopers()

      expect(screen.getByText('Quick Start')).toBeInTheDocument()
      expect(screen.getByText('Python')).toBeInTheDocument()
      expect(screen.getByText('JavaScript')).toBeInTheDocument()
      expect(screen.getByText('REST API')).toBeInTheDocument()
    })

    it('shows quickstart content by default', () => {
      renderDevelopers()

      // Quick Start tab shows "Getting Started" section
      expect(screen.getByText('Getting Started')).toBeInTheDocument()
      expect(screen.getByText('Get your API Key')).toBeInTheDocument()
    })

    it('switches to Python tab on click', () => {
      renderDevelopers()

      fireEvent.click(screen.getByText('Python'))

      expect(screen.getByText('Python Integration')).toBeInTheDocument()
    })

    it('switches to JavaScript tab on click', () => {
      renderDevelopers()

      fireEvent.click(screen.getByText('JavaScript'))

      expect(screen.getByText(/JavaScript\/TypeScript Integration/)).toBeInTheDocument()
    })

    it('switches to REST API tab on click', () => {
      renderDevelopers()

      fireEvent.click(screen.getByText('REST API'))

      expect(screen.getByText('REST API Reference')).toBeInTheDocument()
    })
  })

  describe('Rebranded SDK References', () => {
    it('does not reference old agent-orchestrator-sdk name', () => {
      renderDevelopers()

      // Old name should not appear anywhere
      expect(screen.queryByText(/agent-orchestrator-sdk/)).not.toBeInTheDocument()
    })

    it('shows orchestly branding in JavaScript tab', () => {
      renderDevelopers()

      fireEvent.click(screen.getByText('JavaScript'))

      // Title references the orchestly brand
      expect(screen.getByText(/Orchestly Client/i)).toBeInTheDocument()
    })
  })

  describe('Copy Functionality', () => {
    it('renders copy buttons on code blocks', () => {
      renderDevelopers()

      const copyButtons = screen.getAllByText('Copy')
      expect(copyButtons.length).toBeGreaterThanOrEqual(1)
    })

    it('copies code to clipboard when clicked', async () => {
      renderDevelopers()

      const copyButtons = screen.getAllByText('Copy')
      fireEvent.click(copyButtons[0])

      expect(navigator.clipboard.writeText).toHaveBeenCalled()

      await waitFor(() => {
        expect(screen.getByText('Copied!')).toBeInTheDocument()
      })
    })
  })
})
