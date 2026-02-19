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
  CardFooter,
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
});

type AnalysisFormValues = z.infer<typeof analysisFormSchema>;

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
      ? `${teamName.toUpperCase().replace(/\s+/g, "_").replace(/[^A-Z0-9_]/gi, "")}_${leaderName.toUpperCase().replace(/\s+/g, "_").replace(/[^A-Z0-9_]/gi, "")}_AI_Fix`
      : null;

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
        <div className="mx-auto max-w-2xl space-y-8">
          {/* Page Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-semibold tracking-tight">
                Repository Analysis
              </h1>
              <p className="text-sm text-muted-foreground mt-1">
                Analyze a GitHub repository, detect bugs, and auto-fix issues
                with AI.
              </p>
            </div>
            <Badge variant="outline" className="flex items-center">
              <IconAnalyze className="h-4 w-4 mr-1" />
              AI Agent
            </Badge>
          </div>

          {/* Form Card */}
          <Card className="relative overflow-hidden border border-border/60 bg-card/60 backdrop-blur supports-[backdrop-filter]:bg-card/50">
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-primary/10 opacity-100" />
            <CardHeader className="relative">
              <CardTitle className="flex items-center gap-2">
                <Rocket className="h-5 w-5 text-primary" />
                Start New Analysis
              </CardTitle>
              <CardDescription>
                Provide the repository details to begin the multi-agent code
                analysis pipeline.
              </CardDescription>
            </CardHeader>
            <CardContent className="relative">
              <Form {...form}>
                <form
                  onSubmit={form.handleSubmit(onSubmit)}
                  className="space-y-6"
                >
                  {/* Repository URL */}
                  <FormField
                    control={form.control}
                    name="repo_url"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="flex items-center gap-2">
                          <ExternalLink className="h-4 w-4" />
                          Repository URL
                          <span className="text-destructive">*</span>
                        </FormLabel>
                        <FormControl>
                          <Input
                            placeholder="https://github.com/owner/repo"
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          Public GitHub repository URL to analyze.
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  {/* Team Name */}
                  <FormField
                    control={form.control}
                    name="team_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="flex items-center gap-2">
                          <Users className="h-4 w-4" />
                          Team Name
                          <span className="text-destructive">*</span>
                        </FormLabel>
                        <FormControl>
                          <Input placeholder="e.g. Alpha Squad" {...field} />
                        </FormControl>
                        <FormDescription>
                          Your team name for the analysis branch.
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  {/* Team Leader Name */}
                  <FormField
                    control={form.control}
                    name="team_leader_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="flex items-center gap-2">
                          <User className="h-4 w-4" />
                          Team Leader Name
                          <span className="text-destructive">*</span>
                        </FormLabel>
                        <FormControl>
                          <Input placeholder="e.g. John Doe" {...field} />
                        </FormControl>
                        <FormDescription>
                          The team leader's name for branch naming.
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  {/* Branch preview */}
                  {branchPreview && (
                    <div className="rounded-lg border border-border/60 bg-muted/30 p-3">
                      <p className="text-xs font-medium text-muted-foreground mb-1">
                        Branch Preview
                      </p>
                      <p className="text-sm font-mono flex items-center gap-2">
                        <GitBranch className="h-4 w-4 text-primary" />
                        {branchPreview}
                      </p>
                    </div>
                  )}

                  <Separator />

                  {/* Optional Settings */}
                  <div className="space-y-4">
                    <h3 className="text-sm font-medium text-muted-foreground">
                      Optional Settings
                    </h3>

                    {/* GitHub Token */}
                    <FormField
                      control={form.control}
                      name="github_token"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>GitHub Token (PAT)</FormLabel>
                          <FormControl>
                            <Input
                              type="password"
                              placeholder="ghp_..."
                              {...field}
                            />
                          </FormControl>
                          <FormDescription>
                            Personal Access Token for pushing fixes to the
                            repository. Leave empty to use server default.
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <div className="flex items-center gap-6">
                      {/* Generate Tests */}
                      <FormField
                        control={form.control}
                        name="generate_tests"
                        render={({ field }) => (
                          <FormItem className="flex items-center gap-3 space-y-0">
                            <FormControl>
                              <Switch
                                checked={field.value}
                                onCheckedChange={field.onChange}
                              />
                            </FormControl>
                            <div>
                              <FormLabel className="cursor-pointer">
                                Generate Tests
                              </FormLabel>
                            </div>
                          </FormItem>
                        )}
                      />

                      {/* Push to GitHub */}
                      <FormField
                        control={form.control}
                        name="push_to_github"
                        render={({ field }) => (
                          <FormItem className="flex items-center gap-3 space-y-0">
                            <FormControl>
                              <Switch
                                checked={field.value}
                                onCheckedChange={field.onChange}
                              />
                            </FormControl>
                            <div>
                              <FormLabel className="cursor-pointer">
                                Push to GitHub
                              </FormLabel>
                            </div>
                          </FormItem>
                        )}
                      />
                    </div>
                  </div>

                  <Separator />

                  {/* Submit */}
                  <Button
                    type="submit"
                    className="w-full"
                    size="lg"
                    disabled={isSubmitting}
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Starting Analysis...
                      </>
                    ) : (
                      <>
                        <Rocket className="mr-2 h-4 w-4" />
                        Start Analysis
                      </>
                    )}
                  </Button>
                </form>
              </Form>
            </CardContent>
            <CardFooter className="relative text-xs text-muted-foreground">
              The AI agent will clone, analyze, fix, and optionally push the
              changes to a new branch.
            </CardFooter>
          </Card>
        </div>
      </Main>
    </>
  );
}
