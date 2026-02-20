import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import {
  GitBranch,
  Users,
  User,
  Loader2,
  Rocket,
  ExternalLink,
  Search as SearchIcon,
  Bug,
  Wrench,
  FlaskConical,
  GitPullRequest,
  Shield,
  Zap,
  CheckCircle2,
  Key,
  Settings2,
} from "lucide-react";
import { IconAnalyze } from "@tabler/icons-react";

import { Header } from "@/components/layout/header";
import { Main } from "@/components/layout/main";
import { Search } from "@/components/search";
import { ThemeSwitch } from "@/components/theme-switch";
import { ProfileDropdown } from "@/components/profile-dropdown";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";

import { analysisApi, type AnalysisRequest } from "@/api/analysis";

// ============ FORM SCHEMA ============

const analysisFormSchema = z.object({
  repo_url: z
    .string()
    .min(1, "Repository URL is required")
    .url("Must be a valid URL")
    .regex(
      /^https?:\/\/github\.com\/[\w\-]+\/[\w\-\.]+(?:\.git)?\/?$/,
      "Must be a valid GitHub repository URL (e.g. https://github.com/owner/repo)"
    ),
  team_name: z
    .string()
    .min(2, "Team name must be at least 2 characters")
    .max(50, "Team name must not exceed 50 characters"),
  team_leader_name: z
    .string()
    .min(2, "Team leader name must be at least 2 characters")
    .max(50, "Team leader name must not exceed 50 characters"),
  github_token: z.string().optional(),
  generate_tests: z.boolean(),
  push_to_github: z.boolean(),
  create_pr: z.boolean(),
  auto_merge_on_ci_success: z.boolean(),
});

type AnalysisFormValues = z.infer<typeof analysisFormSchema>;

// ============ FEATURE DATA ============

const features = [
  {
    icon: SearchIcon,
    title: "Deep Code Analysis",
    description: "AI scans every line of code for bugs, vulnerabilities, and code smells",
    color: "text-blue-500",
    bgColor: "bg-blue-500/10",
  },
  {
    icon: Bug,
    title: "Bug Detection",
    description: "Identifies syntax errors, logic bugs, import issues, and type errors",
    color: "text-red-500",
    bgColor: "bg-red-500/10",
  },
  {
    icon: Wrench,
    title: "Auto-Fix Engine",
    description: "Automatically generates and applies fixes for detected issues",
    color: "text-amber-500",
    bgColor: "bg-amber-500/10",
  },
  {
    icon: FlaskConical,
    title: "Test Generation",
    description: "Creates comprehensive test cases to validate fixes and prevent regressions",
    color: "text-green-500",
    bgColor: "bg-green-500/10",
  },
  {
    icon: GitPullRequest,
    title: "PR Creation",
    description: "Automatically creates pull requests with detailed fix descriptions",
    color: "text-purple-500",
    bgColor: "bg-purple-500/10",
  },
  {
    icon: Shield,
    title: "CI/CD Integration",
    description: "Monitors GitHub Actions and auto-merges when CI passes",
    color: "text-cyan-500",
    bgColor: "bg-cyan-500/10",
  },
];

const stats = [
  { value: "5+", label: "AI Agents" },
  { value: "10+", label: "Bug Types" },
  { value: "Auto", label: "Fix & Merge" },
  { value: "Real-time", label: "Monitoring" },
];

// ============ PAGE COMPONENT ============

export default function AnalysisPage() {
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<AnalysisFormValues>({
    resolver: zodResolver(analysisFormSchema) as any,
    defaultValues: {
      repo_url: "",
      team_name: "",
      team_leader_name: "",
      github_token: "",
      generate_tests: true,
      push_to_github: true,
      create_pr: true,
      auto_merge_on_ci_success: true,
    },
  });

  async function onSubmit(values: AnalysisFormValues) {
    setIsSubmitting(true);
    try {
      const payload: AnalysisRequest = {
        repo_url: values.repo_url.trim(),
        team_name: values.team_name.trim(),
        team_leader_name: values.team_leader_name.trim(),
        generate_tests: values.generate_tests,
        push_to_github: values.push_to_github,
        create_pr: values.create_pr,
        auto_merge_on_ci_success: values.auto_merge_on_ci_success,
      };
      if (values.github_token?.trim()) {
        payload.github_token = values.github_token.trim();
      }

      const response = await analysisApi.startAnalysis(payload);
      toast.success("Analysis started successfully!");
      navigate(`/analysis/${response.analysis_id}`);
    } catch (error: any) {
      const detail =
        error?.response?.data?.detail ||
        error?.message ||
        "Failed to start analysis";
      toast.error(detail);
    } finally {
      setIsSubmitting(false);
    }
  }

  // Preview branch name
  const teamName = form.watch("team_name");
  const leaderName = form.watch("team_leader_name");
  const branchPreview =
    teamName && leaderName
      ? `${teamName.toUpperCase().replace(/\s+/g, "_").replace(/[^A-Z0-9_]/gi, "")}_${leaderName.replace(/\s+/g, "_").replace(/[^A-Z0-9_]/gi, "")}_AI_Fix`
      : null;

  const pushEnabled = form.watch("push_to_github");

  return (
    <>
      <Header>
        <Search />
        <div className="ml-auto flex items-center space-x-4">
          <ThemeSwitch />
          <ProfileDropdown />
        </div>
      </Header>
      <Main>
        <div className="w-full space-y-8">
          {/* Hero Section */}
          <div className="relative rounded-2xl border border-border/40 bg-gradient-to-br from-card via-card/95 to-card/90 overflow-hidden">
            <div className="absolute inset-0 bg-grid-white/[0.02] bg-[size:32px_32px]" />
            <div className="absolute top-0 right-0 w-96 h-96 bg-primary/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3" />
            <div className="absolute bottom-0 left-0 w-64 h-64 bg-purple-500/5 rounded-full blur-3xl translate-y-1/2 -translate-x-1/3" />
            
            <div className="relative px-8 py-12 lg:px-12">
              <div className="flex flex-col lg:flex-row lg:items-center gap-6 lg:gap-12">
                <div className="flex-1 space-y-4">
                  <div className="flex items-center gap-3">
                    <Badge variant="secondary" className="bg-primary/10 text-primary border-primary/20 px-3 py-1">
                      <Zap className="h-3 w-3 mr-1.5" />
                      AI-Powered
                    </Badge>
                    <Badge variant="outline" className="px-3 py-1">
                      <IconAnalyze className="h-3 w-3 mr-1.5" />
                      Multi-Agent System
                    </Badge>
                  </div>
                  <h1 className="text-4xl lg:text-5xl font-bold tracking-tight bg-gradient-to-r from-foreground via-foreground to-foreground/70 bg-clip-text">
                    Repository Analysis
                  </h1>
                  <p className="text-lg text-muted-foreground max-w-xl">
                    Analyze GitHub repositories with our intelligent multi-agent system. 
                    Automatically detect bugs, apply fixes, generate tests, and create pull requests.
                  </p>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-4 gap-6 lg:gap-4">
                  {stats.map((stat, i) => (
                    <div key={i} className="text-center">
                      <div className="text-2xl lg:text-3xl font-bold text-primary">{stat.value}</div>
                      <div className="text-xs text-muted-foreground mt-1">{stat.label}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Main Content - Two Column Layout */}
          <div className="grid lg:grid-cols-5 gap-8">
            {/* Left Column - Features */}
            <div className="lg:col-span-2 space-y-6">
              <div>
                <h2 className="text-xl font-semibold mb-2">How It Works</h2>
                <p className="text-sm text-muted-foreground">
                  Our AI agents work together to analyze, fix, and validate your code.
                </p>
              </div>

              <div className="grid gap-4">
                {features.map((feature, i) => (
                  <Card key={i} className="group relative overflow-hidden border-border/50 hover:border-border transition-colors">
                    <div className={`absolute inset-0 ${feature.bgColor} opacity-0 group-hover:opacity-100 transition-opacity`} />
                    <CardContent className="relative flex items-start gap-4 p-4">
                      <div className={`flex-shrink-0 h-10 w-10 rounded-lg ${feature.bgColor} flex items-center justify-center`}>
                        <feature.icon className={`h-5 w-5 ${feature.color}`} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <h3 className="font-medium text-sm">{feature.title}</h3>
                        <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                          {feature.description}
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>

            {/* Right Column - Form */}
            <div className="lg:col-span-3">
              <Card className="relative overflow-hidden border-border/60 shadow-lg">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-purple-500/5" />
                
                <CardHeader className="relative space-y-1 pb-6">
                  <CardTitle className="flex items-center gap-3 text-xl">
                    <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
                      <Rocket className="h-5 w-5 text-primary" />
                    </div>
                    Start New Analysis
                  </CardTitle>
                  <CardDescription className="text-sm">
                    Enter your repository details to begin the automated analysis pipeline.
                  </CardDescription>
                </CardHeader>

                <CardContent className="relative space-y-6">
                  <Form {...form}>
                    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
                      {/* Repository Details Section */}
                      <div className="space-y-5">
                        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                          <GitBranch className="h-4 w-4" />
                          Repository Details
                        </div>
                        
                        {/* Repository URL */}
                        <FormField
                          control={form.control}
                          name="repo_url"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel className="text-sm font-medium">
                                Repository URL <span className="text-destructive">*</span>
                              </FormLabel>
                              <FormControl>
                                <div className="relative">
                                  <ExternalLink className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                                  <Input
                                    placeholder="https://github.com/owner/repo"
                                    className="pl-10 h-11"
                                    {...field}
                                  />
                                </div>
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />

                        {/* Two Column Grid for Team Info */}
                        <div className="grid sm:grid-cols-2 gap-4">
                          <FormField
                            control={form.control}
                            name="team_name"
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel className="text-sm font-medium">
                                  Team Name <span className="text-destructive">*</span>
                                </FormLabel>
                                <FormControl>
                                  <div className="relative">
                                    <Users className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                                    <Input placeholder="Alpha Squad" className="pl-10 h-11" {...field} />
                                  </div>
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />

                          <FormField
                            control={form.control}
                            name="team_leader_name"
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel className="text-sm font-medium">
                                  Team Leader <span className="text-destructive">*</span>
                                </FormLabel>
                                <FormControl>
                                  <div className="relative">
                                    <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                                    <Input placeholder="John Doe" className="pl-10 h-11" {...field} />
                                  </div>
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                        </div>

                        {/* Branch Preview */}
                        {branchPreview && (
                          <div className="rounded-lg border border-primary/20 bg-primary/5 p-4">
                            <div className="flex items-center gap-3">
                              <div className="h-8 w-8 rounded-md bg-primary/10 flex items-center justify-center">
                                <GitBranch className="h-4 w-4 text-primary" />
                              </div>
                              <div className="min-w-0 flex-1">
                                <p className="text-xs font-medium text-muted-foreground">Branch will be created</p>
                                <p className="text-sm font-mono text-primary truncate">{branchPreview}</p>
                              </div>
                              <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0" />
                            </div>
                          </div>
                        )}
                      </div>

                      <Separator />

                      {/* Authentication Section */}
                      <div className="space-y-4">
                        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                          <Key className="h-4 w-4" />
                          Authentication
                        </div>
                        
                        <FormField
                          control={form.control}
                          name="github_token"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel className="text-sm font-medium">GitHub Token (PAT)</FormLabel>
                              <FormControl>
                                <div className="relative">
                                  <Key className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                                  <Input
                                    type="password"
                                    placeholder="ghp_xxxxxxxxxxxx"
                                    className="pl-10 h-11 font-mono"
                                    {...field}
                                  />
                                </div>
                              </FormControl>
                              <FormDescription className="text-xs">
                                Required for pushing fixes. Leave empty to use server default.
                              </FormDescription>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      </div>

                      <Separator />

                      {/* Pipeline Options */}
                      <div className="space-y-4">
                        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                          <Settings2 className="h-4 w-4" />
                          Pipeline Options
                        </div>

                        <div className="grid sm:grid-cols-2 gap-4">
                          <FormField
                            control={form.control}
                            name="generate_tests"
                            render={({ field }) => (
                              <FormItem className="flex items-center justify-between p-4 rounded-lg border border-border/60 hover:border-border transition-colors">
                                <div className="space-y-0.5">
                                  <FormLabel className="text-sm font-medium cursor-pointer flex items-center gap-2">
                                    <FlaskConical className="h-4 w-4 text-green-500" />
                                    Generate Tests
                                  </FormLabel>
                                  <FormDescription className="text-xs">
                                    Create AI test cases
                                  </FormDescription>
                                </div>
                                <FormControl>
                                  <Switch checked={field.value} onCheckedChange={field.onChange} />
                                </FormControl>
                              </FormItem>
                            )}
                          />

                          <FormField
                            control={form.control}
                            name="push_to_github"
                            render={({ field }) => (
                              <FormItem className="flex items-center justify-between p-4 rounded-lg border border-border/60 hover:border-border transition-colors">
                                <div className="space-y-0.5">
                                  <FormLabel className="text-sm font-medium cursor-pointer flex items-center gap-2">
                                    <GitBranch className="h-4 w-4 text-blue-500" />
                                    Push to GitHub
                                  </FormLabel>
                                  <FormDescription className="text-xs">
                                    Create fix branch
                                  </FormDescription>
                                </div>
                                <FormControl>
                                  <Switch checked={field.value} onCheckedChange={field.onChange} />
                                </FormControl>
                              </FormItem>
                            )}
                          />

                          <FormField
                            control={form.control}
                            name="create_pr"
                            render={({ field }) => (
                              <FormItem className={`flex items-center justify-between p-4 rounded-lg border border-border/60 hover:border-border transition-colors ${!pushEnabled ? 'opacity-50' : ''}`}>
                                <div className="space-y-0.5">
                                  <FormLabel className="text-sm font-medium cursor-pointer flex items-center gap-2">
                                    <GitPullRequest className="h-4 w-4 text-purple-500" />
                                    Create PR
                                  </FormLabel>
                                  <FormDescription className="text-xs">
                                    Auto-create pull request
                                  </FormDescription>
                                </div>
                                <FormControl>
                                  <Switch 
                                    checked={field.value} 
                                    onCheckedChange={field.onChange}
                                    disabled={!pushEnabled}
                                  />
                                </FormControl>
                              </FormItem>
                            )}
                          />

                          <FormField
                            control={form.control}
                            name="auto_merge_on_ci_success"
                            render={({ field }) => (
                              <FormItem className={`flex items-center justify-between p-4 rounded-lg border border-border/60 hover:border-border transition-colors ${!pushEnabled ? 'opacity-50' : ''}`}>
                                <div className="space-y-0.5">
                                  <FormLabel className="text-sm font-medium cursor-pointer flex items-center gap-2">
                                    <Shield className="h-4 w-4 text-cyan-500" />
                                    Auto-Merge
                                  </FormLabel>
                                  <FormDescription className="text-xs">
                                    Merge when CI passes
                                  </FormDescription>
                                </div>
                                <FormControl>
                                  <Switch 
                                    checked={field.value} 
                                    onCheckedChange={field.onChange}
                                    disabled={!pushEnabled}
                                  />
                                </FormControl>
                              </FormItem>
                            )}
                          />
                        </div>
                      </div>

                      <Separator />

                      {/* Submit Button */}
                      <Button
                        type="submit"
                        className="w-full h-12 text-base font-medium"
                        size="lg"
                        disabled={isSubmitting}
                      >
                        {isSubmitting ? (
                          <>
                            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                            Starting Analysis...
                          </>
                        ) : (
                          <>
                            <Rocket className="mr-2 h-5 w-5" />
                            Start Analysis
                          </>
                        )}
                      </Button>

                      {/* Footer Note */}
                      <p className="text-xs text-center text-muted-foreground">
                        The AI agent will clone, analyze, fix, and optionally push changes to a new branch.
                      </p>
                    </form>
                  </Form>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </Main>
    </>
  );
}
