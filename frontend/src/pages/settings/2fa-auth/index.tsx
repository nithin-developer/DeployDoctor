import ContentSection from '../components/content-section'
import { TwoFASetup } from './two-fa-setup'

export default function SettingsTwoFA() {
  return (
      <ContentSection
        title='Two-Factor Authentication'
        desc='Secure your account with an additional layer of protection.'
      >
        <TwoFASetup />
      </ContentSection>
  )
}
