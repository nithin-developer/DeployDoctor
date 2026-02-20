import { IconShieldLock, IconAnalyze } from "@tabler/icons-react";
import { Settings } from "lucide-react";

import { IconPalette, IconTool, IconLock } from "@tabler/icons-react";
import { type SidebarData } from "../types";
import Logo from "@/assets/vvce.png";

export const sidebarData: SidebarData = {
  user: {
    full_name: "User",
    email: "user@example.com",
    avatar: "",
  },
  teams: [
    {
      name: "DeployDoctor",
      logo: Logo,
      plan: "RIFT 2026 DevOps Agent",
    },
  ],
  navGroups: [
    {
      title: "Features",
      items: [
        // {
        //   title: "Dashboard",
        //   url: "/",
        //   icon: IconLayoutDashboard,
        // },
        {
          title: "Repository Analysis",
          url: "/analysis",
          icon: IconAnalyze,
        },
      ],
    },
    {
      title: "Management",
      items: [
        {
          title: "Settings",
          icon: Settings,
          items: [
            {
              title: "Account",
              url: "/settings/account",
              icon: IconTool,
            },
            {
              title: "Appearance",
              url: "/settings/appearance",
              icon: IconPalette,
            },
            {
              title: "Security",
              url: "/settings/security",
              icon: IconLock,
            },
            {
              title: "2-FA Authentication",
              url: "/settings/two-factor-authentication",
              icon: IconShieldLock,
            },
          ],
        },
      ],
    },
  ],
};
