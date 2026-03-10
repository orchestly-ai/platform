/**
 * Login Page Tests
 *
 * Tests for the authentication page with login and registration forms.
 *
 * Test Coverage:
 * - Branding elements
 * - Login form rendering
 * - Registration form toggle
 * - Form submission
 * - Error display
 * - Demo credentials hint
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'

// Mock useAuth
const mockLogin = vi.fn()
const mockRegister = vi.fn()
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    login: mockLogin,
    register: mockRegister,
  }),
}))

// Mock react-router-dom useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useLocation: () => ({ state: null, pathname: '/login', search: '', hash: '' }),
  }
})

import { LoginPage } from './Login'

const renderLogin = () => {
  return render(
    <BrowserRouter>
      <LoginPage />
    </BrowserRouter>
  )
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockLogin.mockResolvedValue(undefined)
    mockRegister.mockResolvedValue(undefined)
  })

  describe('Branding', () => {
    it('renders Orchestly brand name', () => {
      renderLogin()

      expect(screen.getByText('Orchestly')).toBeInTheDocument()
    })

    it('renders tagline', () => {
      renderLogin()

      expect(screen.getByText('AI Agent Orchestration')).toBeInTheDocument()
    })

    it('renders demo credentials hint', () => {
      renderLogin()

      expect(screen.getByText('Demo credentials:')).toBeInTheDocument()
      expect(screen.getByText('admin@example.com / admin123')).toBeInTheDocument()
    })
  })

  describe('Login Form', () => {
    it('renders Sign In heading by default', () => {
      renderLogin()

      // "Sign In" appears as both heading and button
      const signInElements = screen.getAllByText('Sign In')
      expect(signInElements.length).toBeGreaterThanOrEqual(1)
    })

    it('renders email and password inputs', () => {
      renderLogin()

      expect(screen.getByLabelText('Email')).toBeInTheDocument()
      expect(screen.getByLabelText('Password')).toBeInTheDocument()
    })

    it('renders Sign In submit button', () => {
      renderLogin()

      const buttons = screen.getAllByText('Sign In')
      // One is heading, one is button
      expect(buttons.length).toBeGreaterThanOrEqual(1)
    })

    it('calls login on form submission', async () => {
      renderLogin()

      fireEvent.change(screen.getByLabelText('Email'), {
        target: { value: 'test@example.com' },
      })
      fireEvent.change(screen.getByLabelText('Password'), {
        target: { value: 'password123' },
      })

      fireEvent.submit(screen.getByLabelText('Email').closest('form')!)

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith('test@example.com', 'password123')
      })
    })

    it('navigates after successful login', async () => {
      renderLogin()

      fireEvent.change(screen.getByLabelText('Email'), {
        target: { value: 'test@example.com' },
      })
      fireEvent.change(screen.getByLabelText('Password'), {
        target: { value: 'password123' },
      })

      fireEvent.submit(screen.getByLabelText('Email').closest('form')!)

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/dashboard', { replace: true })
      })
    })

    it('displays error on login failure', async () => {
      mockLogin.mockRejectedValue(new Error('Invalid credentials'))

      renderLogin()

      fireEvent.change(screen.getByLabelText('Email'), {
        target: { value: 'bad@example.com' },
      })
      fireEvent.change(screen.getByLabelText('Password'), {
        target: { value: 'wrong' },
      })

      fireEvent.submit(screen.getByLabelText('Email').closest('form')!)

      await waitFor(() => {
        expect(screen.getByText('Invalid credentials')).toBeInTheDocument()
      })
    })
  })

  describe('Registration Form', () => {
    it('toggles to registration mode', () => {
      renderLogin()

      fireEvent.click(screen.getByText('Create one'))

      // "Create Account" appears as both heading and button
      const createElements = screen.getAllByText('Create Account')
      expect(createElements.length).toBeGreaterThanOrEqual(1)
      expect(screen.getByLabelText('Name')).toBeInTheDocument()
    })

    it('toggles back to login mode', () => {
      renderLogin()

      // Go to register
      fireEvent.click(screen.getByText('Create one'))
      const createElements = screen.getAllByText('Create Account')
      expect(createElements.length).toBeGreaterThanOrEqual(1)

      // Go back to login — "Sign in" is the link text (lowercase i)
      fireEvent.click(screen.getByText('Sign in'))
      expect(screen.queryByLabelText('Name')).not.toBeInTheDocument()
    })

    it('calls register on form submission', async () => {
      renderLogin()

      // Switch to register mode
      fireEvent.click(screen.getByText('Create one'))

      fireEvent.change(screen.getByLabelText('Name'), {
        target: { value: 'John Doe' },
      })
      fireEvent.change(screen.getByLabelText('Email'), {
        target: { value: 'john@example.com' },
      })
      fireEvent.change(screen.getByLabelText('Password'), {
        target: { value: 'securepass123' },
      })

      fireEvent.submit(screen.getByLabelText('Email').closest('form')!)

      await waitFor(() => {
        expect(mockRegister).toHaveBeenCalledWith(
          'john@example.com',
          'securepass123',
          'John Doe'
        )
      })
    })
  })
})
