import { useState, useCallback } from "react";
import {
  GraduationCap,
  CheckCircle2,
  Play,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  Send,
  Sparkles,
  Clock,
  Award,
  AlertCircle,
  BookOpen,
} from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { API_BASE, mutationFetch } from "@/lib/queryClient";
import { SectionHeader, Card, CardContent } from "@/components/ui-widgets";

// ---- Types ----

interface TrainingStep {
  id?: string;
  title: string;
  content?: string;
  bullets?: string[];
  cta_text?: string;
  cta_action?: string;
  scenario_card?: Record<string, any>;
  sample_recommendation?: {
    action: string;
    reason: string;
    expected_impact: string;
    recommended_action: string;
  };
  interaction?: {
    type: string;
    prompt: string;
    cta_text?: string;
    action_label?: string;
    sample_priorities?: Array<{
      priority: string;
      entity: string;
      reason: string;
      type: string;
      score?: number;
      value?: number;
    }>;
    outcomes?: Array<{ label: string; description?: string }>;
  };
  post_action_content?: string;
  post_action_bullets?: string[];
  post_outcome_content?: string;
  explanation?: string;
  recommended_action?: string;
  recommended_actions?: string[];
}

interface KnowledgeCheck {
  question: string;
  options: string[];
  correct_index: number;
  explanation: string;
}

interface TrainingModule {
  id: string;
  phase: number;
  title: string;
  subtitle: string;
  estimated_minutes: number;
  type: string;
  steps: TrainingStep[];
  knowledge_check: KnowledgeCheck | null;
}

interface SimAction {
  label: string;
  type: string;
  is_simulated?: boolean;
}

interface SimOutcome {
  label: string;
  description?: string;
}

interface SimulationScenario {
  id: string;
  title: string;
  description: string;
  entity: string;
  entity_type: string;
  lead_score?: number;
  opportunity_value?: number;
  last_contact?: string;
  scenario?: string;
  recommended_action?: string;
  actions: SimAction[];
  outcomes: SimOutcome[];
}

interface AdvancedModule {
  id: string;
  title: string;
  description: string;
  estimated_minutes: number;
  is_optional: boolean;
}

interface TrainingProgress {
  started: boolean;
  started_at: string | null;
  completed_modules: string[];
  current_module: string | null;
  current_step: number;
  knowledge_checks_passed: any[];
  knowledge_checks_failed: any[];
  simulations_completed: string[];
  exercises_completed: any[];
  time_spent_minutes: number;
  role: string;
  completed: boolean;
  completed_at: string | null;
  certificate: any;
  percent_complete: number;
  modules_completed: number;
  modules_total: number;
  modules_remaining: number;
  estimated_remaining_minutes: number;
}

interface TrainingData {
  status: string;
  modules: TrainingModule[];
  simulation_scenarios: SimulationScenario[];
  advanced_modules: AdvancedModule[];
  roles: any[];
  progress: TrainingProgress;
  contextual_help: Record<string, any>;
  disclaimer: string;
  sample_prefix: string;
}

interface KcResult {
  module_id: string;
  passed: boolean;
  correct_index: number;
  explanation: string;
}

interface SimResult {
  scenario_id: string;
  message: string;
  outcome: string | null;
}

interface CoachResult {
  response: string;
}

// ---- API helpers ----

async function apiPost(endpoint: string, body?: any) {
  const res = await mutationFetch(endpoint, { method: "POST", body });
  return res.json();
}

// ---- Component ----

export function TrainingPage() {
  const queryClient = useQueryClient();
  const { data: td, isLoading, error } = useQuery<TrainingData>({
    queryKey: [`${API_BASE}/api/training`],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/training`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    staleTime: 30_000,
  });

  const [currentModuleId, setCurrentModuleId] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [kcResult, setKcResult] = useState<KcResult | null>(null);
  const [simResults, setSimResults] = useState<Record<string, SimResult>>({});
  const [coachAnswer, setCoachAnswer] = useState<CoachResult | null>(null);
  const [coachLoading, setCoachLoading] = useState(false);
  const [coachInput, setCoachInput] = useState("");
  const [lastSimAction, setLastSimAction] = useState<string>("");

  const invalidateTraining = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: [`${API_BASE}/api/training`] });
  }, [queryClient]);

  // ---- Actions ----

  const openModule = useCallback((moduleId: string) => {
    setCurrentModuleId(moduleId);
    setCurrentStep(0);
    setKcResult(null);
    apiPost("/api/training/progress", {
      module_id: moduleId,
      step_index: 0,
      completed: false,
    }).then(() => invalidateTraining());
  }, [invalidateTraining]);

  const closeModule = useCallback(() => {
    setCurrentModuleId(null);
    setCurrentStep(0);
    setKcResult(null);
  }, []);

  const nextStep = useCallback(() => {
    setCurrentStep((prev) => {
      const mod = td?.modules.find((m) => m.id === currentModuleId);
      const steps = mod?.steps || [];
      if (prev < steps.length - 1) {
        const next = prev + 1;
        apiPost("/api/training/progress", {
          module_id: currentModuleId,
          step_index: next,
          completed: false,
        }).then(() => invalidateTraining());
        setKcResult(null);
        return next;
      }
      return prev;
    });
  }, [td, currentModuleId, invalidateTraining]);

  const prevStep = useCallback(() => {
    setCurrentStep((prev) => {
      if (prev > 0) {
        setKcResult(null);
        return prev - 1;
      }
      return prev;
    });
  }, []);

  const completeModule = useCallback(() => {
    if (!currentModuleId) return;
    apiPost("/api/training/progress", {
      module_id: currentModuleId,
      step_index: currentStep,
      completed: true,
    }).then(() => {
      setCurrentModuleId(null);
      setCurrentStep(0);
      setKcResult(null);
      invalidateTraining();
    });
  }, [currentModuleId, currentStep, invalidateTraining]);

  const selectKnowledgeCheck = useCallback(
    (moduleId: string, selectedIndex: number) => {
      apiPost("/api/training/knowledge-check", {
        module_id: moduleId,
        selected_index: selectedIndex,
      }).then((result: KcResult) => {
        setKcResult(result);
        invalidateTraining();
      });
    },
    [invalidateTraining]
  );

  const runSimulation = useCallback(
    (scenarioId: string, actionType: string) => {
      setLastSimAction(actionType);
      apiPost("/api/training/simulation", {
        scenario_id: scenarioId,
        action_type: actionType,
        outcome: null,
      }).then((result: SimResult) => {
        setSimResults((prev) => ({ ...prev, [scenarioId]: result }));
        invalidateTraining();
      });
    },
    [invalidateTraining]
  );

  const recordSimOutcome = useCallback(
    (scenarioId: string, outcome: string) => {
      apiPost("/api/training/simulation", {
        scenario_id: scenarioId,
        action_type: lastSimAction,
        outcome,
      }).then((result: SimResult) => {
        setSimResults((prev) => ({ ...prev, [scenarioId]: result }));
        invalidateTraining();
      });
    },
    [lastSimAction, invalidateTraining]
  );

  const askCoach = useCallback(
    (question: string) => {
      if (!question.trim()) return;
      setCoachLoading(true);
      setCoachInput("");
      apiPost("/api/training/coach", { question })
        .then((result: CoachResult) => {
          setCoachAnswer(result);
          setCoachLoading(false);
        })
        .catch(() => setCoachLoading(false));
    },
    []
  );

  const resetProgress = useCallback(() => {
    apiPost("/api/training/reset").then(() => {
      setCurrentModuleId(null);
      setCurrentStep(0);
      setKcResult(null);
      setSimResults({});
      setCoachAnswer(null);
      invalidateTraining();
    });
  }, [invalidateTraining]);

  // ---- Render ----

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-muted-foreground">Loading Training Mode...</div>
      </div>
    );
  }

  if (error || !td) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <AlertCircle className="h-12 w-12 text-destructive" />
        <p className="text-muted-foreground">
          Unable to load training data. Make sure the server is running.
        </p>
        <button
          onClick={() => invalidateTraining()}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90"
        >
          Retry
        </button>
      </div>
    );
  }

  const progress = td.progress || {};
  const isComplete = progress.completed || progress.percent_complete >= 100;

  // Module view
  const activeModule = currentModuleId
    ? td.modules.find((m) => m.id === currentModuleId)
    : null;

  if (activeModule) {
    return (
      <ModuleView
        module={activeModule}
        stepIndex={currentStep}
        kcResult={kcResult}
        onPrev={prevStep}
        onNext={nextStep}
        onComplete={completeModule}
        onBack={closeModule}
        onSelectKc={selectKnowledgeCheck}
      />
    );
  }

  // Main dashboard
  const pct = progress.percent_complete || 0;

  const quickQuestions = [
    "What does this mean?",
    "Why is this important?",
    "How should I use this?",
    "What should I focus on?",
    "Why did this recommendation appear?",
  ];

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Training Mode"
        subtitle="Learn to run your business with the Command Center"
      />

      {/* Disclaimer */}
      <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg p-3 text-sm text-amber-800 dark:text-amber-200">
        {td.disclaimer} -- All training data uses {td.sample_prefix} prefix.
      </div>

      {/* Progress */}
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <GraduationCap className="h-5 w-5 text-primary" />
              <span className="font-semibold">Training Progress</span>
            </div>
            <span className="text-2xl font-bold text-primary">{pct}%</span>
          </div>
          <div className="w-full bg-muted rounded-full h-3 overflow-hidden">
            <div
              className="bg-primary h-full rounded-full transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="mt-2 text-sm text-muted-foreground">
            {progress.modules_completed || 0} of {progress.modules_total || 0}{" "}
            modules -- ~{progress.estimated_remaining_minutes || 0} min remaining
          </div>
        </CardContent>
      </Card>

      {/* Completion certificate */}
      {isComplete && (
        <Card className="border-green-500 dark:border-green-600">
          <CardContent className="p-6 flex items-center gap-4">
            <Award className="h-12 w-12 text-green-600 dark:text-green-400 flex-shrink-0" />
            <div>
              <div className="font-bold text-lg">Training Complete</div>
              <div className="text-sm text-muted-foreground">
                You are ready to operate the Business Command Center. Business
                Owner Certification earned.
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Welcome / Start button */}
      {!progress.started && (
        <Card className="border-primary/30">
          <CardContent className="p-6">
            <div className="flex items-start gap-3 mb-4">
              <Sparkles className="h-6 w-6 text-primary flex-shrink-0 mt-1" />
              <div>
                <div className="text-lg font-bold">
                  Welcome to Your Business Command Center
                </div>
                <div className="text-sm text-muted-foreground mt-1">
                  This platform helps you identify opportunities, prioritize
                  work, follow up consistently, improve client relationships,
                  increase referrals, grow revenue, and stay organized.
                </div>
                <div className="text-sm text-muted-foreground mt-2 flex items-center gap-1">
                  <Clock className="h-4 w-4" /> Estimated training time: 15-20
                  minutes
                </div>
              </div>
            </div>
            <button
              onClick={() => openModule("welcome")}
              className="px-5 py-2.5 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90"
            >
              Start Training
            </button>
          </CardContent>
        </Card>
      )}

      {/* Training Modules */}
      <div>
        <SectionHeader title="Training Modules" />
        <div className="space-y-2">
          {td.modules.map((m, i) => {
            const isCompleted = (progress.completed_modules || []).includes(
              m.id
            );
            const isCurrent = progress.current_module === m.id;
            const phaseLabel =
              m.type === "intro"
                ? "Introduction"
                : m.type === "walkthrough"
                ? "Walkthrough"
                : m.type === "scenario"
                ? "Scenario"
                : m.type === "simulation"
                ? "Simulation"
                : "Module";
            return (
              <div
                key={m.id}
                onClick={() => openModule(m.id)}
                className={`flex items-center gap-3 p-4 rounded-lg border cursor-pointer transition-colors hover:bg-muted/50 ${
                  isCompleted
                    ? "border-green-500/30 bg-green-50/50 dark:bg-green-950/20"
                    : ""
                } ${isCurrent ? "border-primary ring-1 ring-primary/20" : "border-border"}`}
              >
                <div
                  className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                    isCompleted
                      ? "bg-green-600 text-white"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  {isCompleted ? (
                    <CheckCircle2 className="h-5 w-5" />
                  ) : (
                    i + 1
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate">{m.title}</div>
                  <div className="text-sm text-muted-foreground truncate">
                    {m.subtitle} -- {m.estimated_minutes} min -- {phaseLabel}
                  </div>
                </div>
                <div
                  className={`text-sm font-medium px-3 py-1 rounded-full ${
                    isCompleted
                      ? "text-green-600 bg-green-100 dark:bg-green-900/40 dark:text-green-400"
                      : "text-primary bg-primary/10"
                  }`}
                >
                  {isCompleted ? "Done" : "Start"}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Simulation Mode */}
      <div>
        <SectionHeader
          title="Simulation Mode -- Practice Without Risk"
          subtitle="Practice prioritizing, executing actions, and recording outcomes in a safe environment. Simulations do NOT modify your live business data."
        />
        <div className="grid gap-4 md:grid-cols-2">
          {td.simulation_scenarios.map((s) => {
            const isCompleted = (progress.simulations_completed || []).includes(
              s.id
            );
            const simResult = simResults[s.id];
            return (
              <Card key={s.id}>
                <CardContent className="p-4 space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-semibold">{s.title}</div>
                      <div className="text-sm text-muted-foreground">
                        {s.description}
                      </div>
                    </div>
                    {isCompleted && (
                      <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0" />
                    )}
                  </div>
                  {/* Scenario details */}
                  <div className="bg-muted/50 rounded-lg p-3 text-sm space-y-1">
                    {s.scenario && (
                      <div className="text-muted-foreground">{s.scenario}</div>
                    )}
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
                      {s.lead_score !== undefined && (
                        <span>Lead Score: {s.lead_score}/100</span>
                      )}
                      {s.opportunity_value !== undefined && (
                        <span>Value: ${s.opportunity_value.toLocaleString()}</span>
                      )}
                      {s.last_contact && (
                        <span>Last Contact: {s.last_contact}</span>
                      )}
                    </div>
                  </div>
                  {/* Action buttons */}
                  <div className="flex flex-wrap gap-2">
                    {s.actions.map((a) => (
                      <button
                        key={a.type}
                        onClick={() => runSimulation(s.id, a.type)}
                        className="px-3 py-1.5 text-sm border border-border rounded-lg hover:bg-muted transition-colors"
                      >
                        {a.label}
                      </button>
                    ))}
                  </div>
                  {/* Simulation result */}
                  {simResult && simResult.scenario_id === s.id && (
                    <div className="space-y-2">
                      <div className="bg-primary/5 border border-primary/20 rounded-lg p-3 text-sm">
                        {simResult.message}
                      </div>
                      {!simResult.outcome && (
                        <div>
                          <div className="text-xs font-medium text-muted-foreground mb-1">
                            Record the outcome:
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {s.outcomes.map((o) => (
                              <button
                                key={o.label}
                                onClick={() =>
                                  recordSimOutcome(s.id, o.label)
                                }
                                className="px-3 py-1 text-sm border border-border rounded-lg hover:bg-muted transition-colors"
                              >
                                {o.label}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                      {simResult.outcome && (
                        <div className="text-sm text-green-600 dark:text-green-400">
                          Outcome recorded: {simResult.outcome}
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Training Coach */}
      <div>
        <SectionHeader
          title="Training Coach"
          subtitle="Ask me anything about how to use the platform. I answer in beginner-friendly language."
        />
        <Card>
          <CardContent className="p-4 space-y-3">
            <div className="flex flex-wrap gap-2">
              {quickQuestions.map((q) => (
                <button
                  key={q}
                  onClick={() => askCoach(q)}
                  className="px-3 py-1.5 text-sm bg-muted hover:bg-muted/70 rounded-full transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={coachInput}
                onChange={(e) => setCoachInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") askCoach(coachInput);
                }}
                placeholder="Ask your own question..."
                className="flex-1 px-3 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <button
                onClick={() => askCoach(coachInput)}
                disabled={coachLoading}
                className="px-3 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
            {coachLoading && (
              <div className="flex items-center justify-center py-4">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
              </div>
            )}
            {coachAnswer && !coachLoading && (
              <div className="bg-primary/5 border border-primary/20 rounded-lg p-3 text-sm">
                {coachAnswer.response}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Advanced Modules */}
      <div>
        <SectionHeader title="Optional Advanced Modules" />
        <div className="grid gap-3 md:grid-cols-2">
          {td.advanced_modules.map((m) => (
            <Card key={m.id}>
              <CardContent className="p-4">
                <div className="flex items-start gap-2">
                  <BookOpen className="h-5 w-5 text-muted-foreground flex-shrink-0 mt-0.5" />
                  <div>
                    <div className="font-medium">{m.title}</div>
                    <div className="text-sm text-muted-foreground mt-0.5">
                      {m.description}
                    </div>
                    <div className="text-xs text-muted-foreground mt-2 flex items-center gap-1">
                      <Clock className="h-3 w-3" /> {m.estimated_minutes} min --
                      Optional
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Reset */}
      <div className="pt-4">
        <button
          onClick={resetProgress}
          className="px-4 py-2 text-sm border border-border rounded-lg hover:bg-muted transition-colors flex items-center gap-2"
        >
          <RotateCcw className="h-4 w-4" /> Reset Training Progress
        </button>
      </div>
    </div>
  );
}

// ---- Module View Component ----

function ModuleView({
  module,
  stepIndex,
  kcResult,
  onPrev,
  onNext,
  onComplete,
  onBack,
  onSelectKc,
}: {
  module: TrainingModule;
  stepIndex: number;
  kcResult: KcResult | null;
  onPrev: () => void;
  onNext: () => void;
  onComplete: () => void;
  onBack: () => void;
  onSelectKc: (moduleId: string, selectedIndex: number) => void;
}) {
  const steps = module.steps || [];
  const step = steps[stepIndex] || steps[0];

  if (!step) {
    return (
      <div className="flex items-center justify-center min-h-[200px] text-muted-foreground">
        No steps available
      </div>
    );
  }

  const kcPassed =
    !module.knowledge_check ||
    (kcResult && kcResult.passed && kcResult.module_id === module.id);
  const isLastStep = stepIndex >= steps.length - 1;

  return (
    <div className="space-y-4">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm">
        <button
          onClick={onBack}
          className="flex items-center gap-1 text-primary hover:underline"
        >
          <ChevronLeft className="h-4 w-4" /> Back to Training
        </button>
        <span className="text-muted-foreground">/</span>
        <span className="text-muted-foreground">{module.title}</span>
      </div>

      {/* Step indicator */}
      <div className="text-sm text-muted-foreground">
        Step {stepIndex + 1} of {steps.length}
      </div>

      {/* Step card */}
      <Card>
        <CardContent className="p-6 space-y-4">
          <div className="text-xl font-bold">{step.title}</div>

          {step.content && (
            <div className="text-sm text-muted-foreground leading-relaxed">
              {step.content}
            </div>
          )}

          {step.bullets && step.bullets.length > 0 && (
            <ul className="space-y-1.5">
              {step.bullets.map((b, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 text-sm"
                >
                  <CheckCircle2 className="h-4 w-4 text-primary flex-shrink-0 mt-0.5" />
                  <span>{b}</span>
                </li>
              ))}
            </ul>
          )}

          {/* Scenario card */}
          {step.scenario_card && (
            <ScenarioCard card={step.scenario_card} />
          )}

          {/* Sample recommendation */}
          {step.sample_recommendation && (
            <div className="bg-primary/5 border border-primary/20 rounded-lg p-4 space-y-2">
              <div className="text-sm font-semibold text-primary">
                Recommended Action
              </div>
              <div className="font-medium">
                {step.sample_recommendation.action}
              </div>
              <div className="text-sm text-muted-foreground">
                {step.sample_recommendation.reason}
              </div>
              <div className="text-sm">
                <strong>Expected Impact:</strong>{" "}
                {step.sample_recommendation.expected_impact}
              </div>
              <div className="text-sm">
                <strong>Action:</strong>{" "}
                {step.sample_recommendation.recommended_action}
              </div>
            </div>
          )}

          {/* Interaction */}
          {step.interaction && (
            <div className="space-y-3">
              <div className="font-medium">
                {step.interaction.prompt}
              </div>
              {step.interaction.type === "click_priority" &&
                step.interaction.sample_priorities && (
                  <div className="space-y-2">
                    {step.interaction.sample_priorities.map((p, i) => (
                      <div
                        key={i}
                        onClick={onNext}
                        className="flex items-start gap-3 p-3 border border-border rounded-lg cursor-pointer hover:bg-muted/50"
                      >
                        <div className="flex-shrink-0 w-7 h-7 rounded bg-primary text-primary-foreground flex items-center justify-center text-xs font-bold">
                          {p.priority}
                        </div>
                        <div>
                          <div className="font-medium">{p.entity}</div>
                          <div className="text-sm text-muted-foreground">
                            {p.reason}
                          </div>
                          <div className="text-xs text-muted-foreground mt-1">
                            {p.type}
                            {p.score ? ` -- Score: ${p.score}` : ""}
                            {p.value ? ` -- Value: $${p.value.toLocaleString()}` : ""}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              {step.interaction.type === "click_recommendation" && (
                <button
                  onClick={onNext}
                  className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90"
                >
                  {step.interaction.cta_text || "Click here"}
                </button>
              )}
              {step.interaction.type === "simulate_action" && (
                <div className="space-y-1">
                  <button
                    onClick={onNext}
                    className="px-4 py-2 border border-border rounded-lg hover:bg-muted"
                  >
                    {step.interaction.action_label}
                  </button>
                  <div className="text-xs text-muted-foreground">
                    Simulated -- no real call is made
                  </div>
                </div>
              )}
              {step.interaction.type === "select_outcome" &&
                step.interaction.outcomes && (
                  <div className="space-y-2">
                    {step.interaction.outcomes.map((o, i) => (
                      <div
                        key={i}
                        onClick={onNext}
                        className="p-3 border border-border rounded-lg cursor-pointer hover:bg-muted/50"
                      >
                        <div className="font-medium text-sm">{o.label}</div>
                        {o.description && (
                          <div className="text-xs text-muted-foreground mt-0.5">
                            {o.description}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              {step.interaction.type === "create_followup" && (
                <button
                  onClick={onNext}
                  className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90"
                >
                  {step.interaction.cta_text || "Create"}
                </button>
              )}
            </div>
          )}

          {/* Post-action content */}
          {step.post_action_content && (
            <div className="text-sm text-muted-foreground">
              {step.post_action_content}
            </div>
          )}
          {step.post_action_bullets && step.post_action_bullets.length > 0 && (
            <ul className="space-y-1.5">
              {step.post_action_bullets.map((b, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 text-sm"
                >
                  <CheckCircle2 className="h-4 w-4 text-primary flex-shrink-0 mt-0.5" />
                  <span>{b}</span>
                </li>
              ))}
            </ul>
          )}
          {step.post_outcome_content && (
            <div className="text-sm text-muted-foreground">
              {step.post_outcome_content}
            </div>
          )}
          {step.explanation && (
            <div className="text-sm bg-muted/50 rounded-lg p-3">
              <strong>Why this matters:</strong> {step.explanation}
            </div>
          )}
          {step.recommended_action && (
            <div className="text-sm">
              <strong>Recommended Action:</strong> {step.recommended_action}
            </div>
          )}
          {step.recommended_actions && step.recommended_actions.length > 0 && (
            <div className="text-sm">
              <strong>Recommended Actions:</strong>
              <ol className="list-decimal list-inside mt-1 space-y-0.5">
                {step.recommended_actions.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ol>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Knowledge check */}
      {module.knowledge_check && isLastStep && (
        <Card className="border-primary/30">
          <CardContent className="p-4 space-y-3">
            <div className="font-semibold flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-primary" /> Knowledge Check
            </div>
            <div className="text-sm">{module.knowledge_check.question}</div>
            <div className="space-y-2">
              {module.knowledge_check.options.map((opt, i) => {
                const isCorrect =
                  kcResult &&
                  kcResult.module_id === module.id &&
                  kcResult.correct_index === i;
                return (
                  <div
                    key={i}
                    onClick={() => onSelectKc(module.id, i)}
                    className={`p-3 border rounded-lg cursor-pointer transition-colors text-sm ${
                      isCorrect
                        ? "border-green-500 bg-green-50 dark:bg-green-950/30"
                        : "border-border hover:bg-muted/50"
                    }`}
                  >
                    {opt}
                  </div>
                );
              })}
            </div>
            {kcResult && kcResult.module_id === module.id && (
              <div
                className={`text-sm rounded-lg p-3 ${
                  kcResult.passed
                    ? "bg-green-50 dark:bg-green-950/30 text-green-700 dark:text-green-300"
                    : "bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300"
                }`}
              >
                {kcResult.passed
                  ? `Correct! ${kcResult.explanation}`
                  : `Not quite. ${kcResult.explanation} Try again.`}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={onPrev}
          disabled={stepIndex === 0}
          className="px-4 py-2 border border-border rounded-lg hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1"
        >
          <ChevronLeft className="h-4 w-4" /> Previous
        </button>
        {stepIndex < steps.length - 1 ? (
          <button
            onClick={onNext}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 flex items-center gap-1"
          >
            Next <ChevronRight className="h-4 w-4" />
          </button>
        ) : kcPassed ? (
          <button
            onClick={onComplete}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-1"
          >
            <CheckCircle2 className="h-4 w-4" /> Complete Module
          </button>
        ) : (
          <div className="text-sm text-muted-foreground">
            Complete the knowledge check to finish this module.
          </div>
        )}
      </div>
    </div>
  );
}

// ---- Scenario Card Component ----

function ScenarioCard({ card }: { card: Record<string, any> }) {
  const fields = [
    { key: "name", label: "" },
    { key: "lead_score", label: "Lead Score" },
    { key: "opportunity_value", label: "Opportunity Value" },
    { key: "last_contact", label: "Last Contact" },
    { key: "eligibility", label: "Eligibility" },
    { key: "status", label: "Status" },
    { key: "type", label: "Type" },
    { key: "clv", label: "Client Lifetime Value" },
    { key: "health_score", label: "Health Score" },
    { key: "review_status", label: "Review Status" },
    { key: "referrals_this_year", label: "Referrals This Year" },
    { key: "potential_opportunity", label: "Potential Opportunity" },
    { key: "monthly_goal", label: "Monthly Goal" },
    { key: "forecast", label: "Forecast" },
    { key: "gap", label: "Gap" },
    { key: "current_booked", label: "Currently Booked" },
    { key: "pipeline_value", label: "Pipeline Value" },
    { key: "close_rate", label: "Close Rate" },
    { key: "content_pieces", label: "Content Pieces" },
    { key: "compliance", label: "Compliance" },
    { key: "channels", label: "Channels" },
    { key: "biggest_win", label: "Biggest Win" },
    { key: "biggest_concern", label: "Biggest Concern" },
    { key: "biggest_opportunity", label: "Biggest Opportunity" },
    { key: "overall_score", label: "Business Health Score", highlight: true },
  ];

  const validFields = fields.filter((f) => card[f.key] !== undefined && card[f.key] !== null);
  const categories = card.categories || [];
  const changes = card.changes || [];
  const weeklyFocus = card.weekly_focus || [];

  return (
    <div className="bg-muted/30 border border-border rounded-lg p-4 space-y-3">
      {card.name && (
        <div className="font-bold text-lg">{card.name}</div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5">
        {validFields
          .filter((f) => f.label)
          .map((f) => (
            <div
              key={f.key}
              className={`flex items-center justify-between text-sm ${
                f.highlight ? "font-bold" : ""
              }`}
            >
              <span className="text-muted-foreground">{f.label}</span>
              <span>{String(card[f.key])}</span>
            </div>
          ))}
      </div>
      {categories.length > 0 && (
        <div className="space-y-1 pt-2 border-t border-border">
          {categories.map((c: any, i: number) => (
            <div
              key={i}
              className="flex items-center justify-between text-sm"
            >
              <span className="text-muted-foreground">
                {c.name} ({c.weight})
              </span>
              <span>{c.score}/100</span>
            </div>
          ))}
        </div>
      )}
      {changes.length > 0 && (
        <div className="space-y-1 pt-2 border-t border-border">
          {changes.map((c: any, i: number) => {
            const dir =
              c.direction === "up"
                ? "\u2191"
                : c.direction === "down"
                ? "\u2193"
                : "\u2192";
            return (
              <div
                key={i}
                className={`text-sm ${
                  c.meaningful ? "text-primary" : "text-muted-foreground"
                }`}
              >
                {c.metric} {dir} {c.change} -- {c.explanation}
              </div>
            );
          })}
        </div>
      )}
      {weeklyFocus.length > 0 && (
        <div className="pt-2 border-t border-border">
          <div className="text-sm font-medium mb-1">Weekly Focus</div>
          <ol className="list-decimal list-inside text-sm space-y-0.5">
            {weeklyFocus.map((f: string, i: number) => (
              <li key={i}>{f}</li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
