"use client"

import { useState, useEffect } from "react"
import { InsuranceHeader } from "@/components/insurance/insurance-header"
import { StepBar } from "@/components/insurance/step-bar"
import { StepUserInfo } from "@/components/insurance/step-user-info"
import { StepExtraInfo } from "@/components/insurance/step-extra-info"
import { StepCaptcha } from "@/components/insurance/step-captcha"
import { StepAuth } from "@/components/insurance/step-auth"
import { StepLoading } from "@/components/insurance/step-loading"
import { StepResult } from "@/components/insurance/step-result"
import { StepHistory } from "@/components/insurance/step-history"
import { INSURANCE_DEMO_CUSTOMER, INSURANCE_DEMO_DATA } from "@/lib/insurance-demo-data"
import { getSavedUser, saveUser, clearSavedUser, maskName, maskPhone, type SavedUser } from "@/lib/user-storage"

export type Step = "demo" | "welcome" | "history" | 1 | 2 | 3 | 6 | 7

export interface InsuranceState {
  name: string
  birth: string
  phone: string
  idBack7: string
  telecom: string
  email: string
  regId: string
  regPw: string
  authMethod: "pass" | "sms"
  sessionId: string | null
  captchaImage: string | null
}

const INITIAL_STATE: InsuranceState = {
  name: "", birth: "", phone: "", idBack7: "",
  telecom: "0", email: "", regId: "", regPw: "",
  authMethod: "pass", sessionId: null, captchaImage: null,
}

export default function InsurancePage() {
  const [step, setStep] = useState<Step>("demo")
  const [demoRevision, setDemoRevision] = useState(0)
  const [state, setState] = useState<InsuranceState>(INITIAL_STATE)
  const [showExtra, setShowExtra] = useState(false)
  const [savedUser, setSavedUser] = useState<SavedUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [registrationReconnectRequired, setRegistrationReconnectRequired] = useState(false)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [resultData, setResultData] = useState<any>(null)

  // Check for saved user on mount
  useEffect(() => {
    const user = getSavedUser()
    if (user) {
      setSavedUser(user)
      // Pre-fill state with saved user data
      setState(prev => ({
        ...prev,
        name: user.name,
        birth: user.birth,
        phone: user.phone,
      }))
    }
    setIsLoading(false)
  }, [])

  function updateState(patch: Partial<InsuranceState>) {
    setState(prev => ({ ...prev, ...patch }))
  }

  function handleLoginWithSaved() {
    // Use saved user info to start fresh session
    if (savedUser) {
      setState(prev => ({
        ...prev,
        name: savedUser.name,
        birth: savedUser.birth,
        phone: savedUser.phone,
      }))
    }
    // Go directly to loading/query step
    setStep(6)
  }

  function handleNewRegistration() {
    // Clear saved user and start fresh
    clearSavedUser()
    setSavedUser(null)
    setState(INITIAL_STATE)
    setRegistrationReconnectRequired(false)
    setStep(1)
  }

  function handleRegistrationRequired() {
    clearSavedUser()
    setSavedUser(null)
    setState(prev => ({ ...prev, sessionId: null, regId: "", regPw: "" }))
    setShowExtra(true)
    setRegistrationReconnectRequired(true)
    setStep(1)
  }

  function handleSuccessfulRegistration() {
    // Save user data for future logins
    saveUser({
      name: state.name,
      birth: state.birth,
      phone: state.phone,
    })
    setSavedUser({
      name: state.name,
      birth: state.birth,
      phone: state.phone,
      savedAt: Date.now(),
    })
    setRegistrationReconnectRequired(false)
    setStep(6)
  }

  function reset() {
    // Keep saved user but reset current session
    setStep("welcome")
    setShowExtra(false)
    setResultData(null)
  }

  function fullLogout() {
    clearSavedUser()
    setSavedUser(null)
    setState(INITIAL_STATE)
    setStep("welcome")
    setShowExtra(false)
    setResultData(null)
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <InsuranceHeader />
        <main className="flex min-h-[60vh] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </main>
      </div>
    )
  }

  if (step === "demo") {
    return (
      <div className="insurance-shell min-h-screen bg-[#f3f0e8]">
        <StepResult
          key={`insurance-demo-${demoRevision}`}
          data={INSURANCE_DEMO_DATA}
          demoMode
          onReset={() => setDemoRevision((current) => current + 1)}
          onConnect={() => setStep("welcome")}
          userName={INSURANCE_DEMO_CUSTOMER.name}
        />
      </div>
    )
  }

  if (step === 7) {
    return (
      <div className="insurance-shell min-h-screen bg-[#f3f0e8]">
        <StepResult
          data={resultData}
          onReset={reset}
          onLogout={fullLogout}
          userName={savedUser?.name || state.name}
          connectionProfile={{
            userName: savedUser?.name || state.name,
            phoneNo: savedUser?.phone || state.phone,
            telecom: state.telecom,
          }}
        />
      </div>
    )
  }

  return (
    <div className="insurance-shell min-h-screen bg-[#f3f0e8]">
      <InsuranceHeader />
      <main className="mx-auto max-w-xl px-4 pb-20 pt-10 sm:px-6">

        {/* Welcome Screen */}
        {step === "welcome" && (
          <div className="animate-fade-in">
            {savedUser ? (
              // Returning user
              <div className="rounded-[28px] border border-[#d8d3c8] bg-[#fffdf8] p-7 shadow-[0_24px_70px_rgba(23,33,31,0.08)] sm:p-9">
                <div className="mb-6 text-center">
                  <div className="mb-2 inline-flex h-12 w-12 items-center justify-center rounded-full border border-[#d8d3c8] bg-[#edf4ef]">
                    <span className="text-xl text-primary">✓</span>
                  </div>
                  <h2 className="mt-4 font-serif text-xl font-bold text-foreground">
                    다시 오셨군요!
                  </h2>
                  <p className="mt-2 text-sm text-muted-foreground">
                    저장된 정보로 바로 조회하실 수 있습니다
                  </p>
                </div>

                <div className="mb-6 rounded-2xl border border-border bg-white/60 px-4 py-4">
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">이름</span>
                      <p className="font-medium text-foreground">{maskName(savedUser.name)}</p>
                    </div>
                    <div>
                      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">전화번호</span>
                      <p className="font-medium text-foreground">{maskPhone(savedUser.phone)}</p>
                    </div>
                    <div>
                      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">생년월일</span>
                      <p className="font-medium text-foreground">{savedUser.birth.slice(0, 4)}.**.**</p>
                    </div>
                    <div>
                      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">저장일</span>
                      <p className="font-medium text-foreground">
                        {new Date(savedUser.savedAt).toLocaleDateString("ko-KR")}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="space-y-3">
                  <button
                    onClick={handleLoginWithSaved}
                    className="w-full rounded-xl bg-[#17211f] py-3.5 text-sm font-semibold text-white transition-colors hover:bg-[#25332f]"
                  >
                    내 보험 바로 조회하기
                  </button>
                  <button
                    onClick={handleNewRegistration}
                    className="w-full rounded-xl border border-[#d8d3c8] bg-white py-3.5 text-sm font-medium text-[#17211f] transition-colors hover:bg-[#f3f0e8]"
                  >
                    다른 정보로 새로 등록
                  </button>
                  <button
                    onClick={() => setStep("history")}
                    className="w-full rounded-xl border border-transparent bg-transparent py-3 text-sm font-medium text-[#6e6a62] transition-colors hover:border-[#d8d3c8] hover:bg-white hover:text-[#17211f]"
                  >
                    이전 조회 이력 보기
                  </button>
                </div>

                <p className="mt-4 text-center text-[10px] text-muted-foreground">
                  정보는 이 기기에만 저장되며 30일 후 자동 삭제됩니다
                </p>
              </div>
            ) : (
              // New user
              <div className="rounded-[28px] border border-[#d8d3c8] bg-[#fffdf8] p-7 shadow-[0_24px_70px_rgba(23,33,31,0.08)] sm:p-9">
                <div className="mb-6 text-center">
                  <div className="mb-2 inline-flex h-12 w-12 items-center justify-center rounded-full border border-[#d8d3c8] bg-[#fff1ed]">
                    <span className="text-xl text-primary">!</span>
                  </div>
                  <h2 className="mt-4 font-serif text-xl font-bold text-foreground">
                    처음이시군요!
                  </h2>
                  <p className="mt-2 text-sm text-muted-foreground">
                    본인인증 후 가입하신 모든 보험을 조회할 수 있습니다
                  </p>
                </div>

                <div className="mb-6 space-y-3 rounded-2xl border border-border bg-white/60 px-4 py-4 text-sm text-muted-foreground">
                  <div className="flex items-start gap-3">
                    <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-primary/10 text-[10px] font-bold text-primary">1</span>
                    <span>기본 정보 입력 (이름, 생년월일, 전화번호)</span>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-primary/10 text-[10px] font-bold text-primary">2</span>
                    <span>본인인증 (PASS 또는 SMS)</span>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-primary/10 text-[10px] font-bold text-primary">3</span>
                    <span>보험 상품 조회 및 약관 분석</span>
                  </div>
                </div>

                <button
                  onClick={() => setStep(1)}
                  className="w-full rounded-xl bg-[#d94835] py-3.5 text-sm font-semibold text-white transition-colors hover:bg-[#bd3828]"
                >
                  시작하기
                </button>

                <p className="mt-4 text-center text-[10px] text-muted-foreground">
                  한 번 등록하면 다음에는 바로 조회할 수 있습니다
                </p>
              </div>
            )}
          </div>
        )}

        {/* Query history (returning users) */}
        {step === "history" && savedUser && (
          <StepHistory
            phone={savedUser.phone}
            birth={savedUser.birth}
            onView={(data) => {
              setResultData(data)
              setStep(7)
            }}
            onBack={() => setStep("welcome")}
          />
        )}

        {/* Registration Steps */}
        {typeof step === "number" && step >= 1 && step <= 3 && (
          <StepBar current={step} total={3} />
        )}

        {step === 1 && (
          <>
            {registrationReconnectRequired && (
              <div className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-900">
                서버 저장정보가 갱신되어 한 번만 다시 연결해야 합니다. 기본정보는 그대로 두었으니 아래에서 본인인증을 완료해주세요.
              </div>
            )}
            <StepUserInfo
              state={state}
              updateState={updateState}
              onNewUser={() => setShowExtra(true)}
              onExistingUser={(sid) => {
                updateState({ sessionId: sid })
                handleSuccessfulRegistration()
              }}
            />
            {showExtra && (
              <StepExtraInfo
                state={state}
                updateState={updateState}
                onCaptcha={() => setStep(2)}
                onAuthWait={() => setStep(3)}
                onRegistered={handleSuccessfulRegistration}
              />
            )}
          </>
        )}

        {step === 2 && (
          <StepCaptcha
            state={state}
            onSuccess={() => setStep(3)}
            onBack={() => setStep(1)}
          />
        )}

        {step === 3 && (
          <StepAuth
            state={state}
            onRegistered={handleSuccessfulRegistration}
            onCancel={() => setStep(1)}
          />
        )}

        {step === 6 && (
          <StepLoading
            state={state}
            onSuccess={(data) => {
              setResultData(data)
              setStep(7)
            }}
            onError={() => setStep("welcome")}
            onRegistrationRequired={handleRegistrationRequired}
          />
        )}

      </main>
    </div>
  )
}
