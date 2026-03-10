/**
 * OnboardingWizard Tests
 *
 * Tests:
 * - Renders all 4 steps
 * - Navigation between steps (next/back)
 * - Dismiss button works
 * - Complete callback fired on final step
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { OnboardingWizard } from './OnboardingWizard'

describe('OnboardingWizard', () => {
  const mockOnComplete = vi.fn()
  const mockOnDismiss = vi.fn()

  const renderWizard = () =>
    render(
      <OnboardingWizard
        onComplete={mockOnComplete}
        onDismiss={mockOnDismiss}
      />
    )

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the wizard container', () => {
    renderWizard()
    expect(screen.getByTestId('onboarding-wizard')).toBeInTheDocument()
  })

  it('starts on the Welcome step', () => {
    renderWizard()
    expect(screen.getByTestId('step-welcome')).toBeInTheDocument()
    expect(screen.getByText('Welcome to Orchestly')).toBeInTheDocument()
  })

  it('navigates to step 2 (Connect) on Next click', () => {
    renderWizard()
    fireEvent.click(screen.getByTestId('next-button'))
    expect(screen.getByTestId('step-connect')).toBeInTheDocument()
    expect(screen.getByText('Connect an Integration')).toBeInTheDocument()
  })

  it('navigates to step 3 (Template) on second Next click', () => {
    renderWizard()
    fireEvent.click(screen.getByTestId('next-button'))
    fireEvent.click(screen.getByTestId('next-button'))
    expect(screen.getByTestId('step-template')).toBeInTheDocument()
    expect(screen.getByText('Choose a Template')).toBeInTheDocument()
  })

  it('navigates to step 4 (Launch) on third Next click', () => {
    renderWizard()
    fireEvent.click(screen.getByTestId('next-button'))
    fireEvent.click(screen.getByTestId('next-button'))
    fireEvent.click(screen.getByTestId('next-button'))
    expect(screen.getByTestId('step-launch')).toBeInTheDocument()
    expect(screen.getByText('Ready to Launch!')).toBeInTheDocument()
  })

  it('navigates back from step 2 to step 1', () => {
    renderWizard()
    fireEvent.click(screen.getByTestId('next-button'))
    expect(screen.getByTestId('step-connect')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('back-button'))
    expect(screen.getByTestId('step-welcome')).toBeInTheDocument()
  })

  it('back button is disabled on first step', () => {
    renderWizard()
    const backButton = screen.getByTestId('back-button')
    expect(backButton).toBeDisabled()
  })

  it('dismiss button calls onDismiss', () => {
    renderWizard()
    fireEvent.click(screen.getByTestId('dismiss-button'))
    expect(mockOnDismiss).toHaveBeenCalledTimes(1)
  })

  it('launch button on final step calls onComplete', () => {
    renderWizard()
    // Navigate to last step
    fireEvent.click(screen.getByTestId('next-button'))
    fireEvent.click(screen.getByTestId('next-button'))
    fireEvent.click(screen.getByTestId('next-button'))

    // Click launch
    fireEvent.click(screen.getByTestId('launch-button'))
    expect(mockOnComplete).toHaveBeenCalledTimes(1)
  })

  it('shows all 4 step indicators', () => {
    renderWizard()
    expect(screen.getByTestId('step-indicator-0')).toBeInTheDocument()
    expect(screen.getByTestId('step-indicator-1')).toBeInTheDocument()
    expect(screen.getByTestId('step-indicator-2')).toBeInTheDocument()
    expect(screen.getByTestId('step-indicator-3')).toBeInTheDocument()
  })

  it('shows integration connect buttons on step 2', () => {
    renderWizard()
    fireEvent.click(screen.getByTestId('next-button'))
    expect(screen.getByTestId('connect-slack')).toBeInTheDocument()
    expect(screen.getByTestId('connect-github')).toBeInTheDocument()
  })

  it('shows template options on step 3', () => {
    renderWizard()
    fireEvent.click(screen.getByTestId('next-button'))
    fireEvent.click(screen.getByTestId('next-button'))
    expect(screen.getByTestId('template-customer-support')).toBeInTheDocument()
    expect(screen.getByTestId('template-content-pipeline')).toBeInTheDocument()
    expect(screen.getByTestId('template-data-processing')).toBeInTheDocument()
  })
})
