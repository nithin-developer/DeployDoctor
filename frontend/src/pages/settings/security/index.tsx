import ContentSection from "../components/content-section";
import { PasswordForm } from "./password-form";

export default function SettingsSecurity() {
  return (
    <ContentSection title="Password" desc="Manage your password settings.">
      <PasswordForm />
    </ContentSection>
  );
}
