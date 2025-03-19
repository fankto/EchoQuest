import Link from 'next/link'
import { DashboardHeader } from '@/components/dashboard/dashboard-header'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { CalendarIcon, FileIcon, MessageSquare, PlusIcon } from 'lucide-react'
import { RecentInterviews } from '@/components/dashboard/recent-interviews'
import { RecentQuestionnaires } from '@/components/dashboard/recent-questionnaires'
import { CreditSummary } from '@/components/dashboard/credit-summary'
import { StatsCards } from '@/components/dashboard/stats-cards'

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col">
      <DashboardHeader />
      
      <main className="flex-1 space-y-4 p-8 pt-6">
        <div className="flex items-center justify-between space-y-2">
          <h2 className="text-3xl font-bold tracking-tight">Dashboard</h2>
          <div className="flex items-center space-x-2">
            <Link href="/interviews/new">
              <Button>
                <PlusIcon className="mr-2 h-4 w-4" />
                New Interview
              </Button>
            </Link>
          </div>
        </div>
        
        <Tabs defaultValue="overview" className="space-y-4">
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="interviews">Interviews</TabsTrigger>
            <TabsTrigger value="questionnaires">Questionnaires</TabsTrigger>
          </TabsList>
          
          <TabsContent value="overview" className="space-y-4">
            <StatsCards />
            
            <div className="grid gap-4 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Recent Interviews</CardTitle>
                  <CardDescription>
                    Your most recent interview transcriptions and analyses
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <RecentInterviews />
                </CardContent>
                <CardFooter>
                  <Link href="/interviews">
                    <Button variant="outline">View All</Button>
                  </Link>
                </CardFooter>
              </Card>
              
              <Card>
                <CardHeader>
                  <CardTitle>Recent Questionnaires</CardTitle>
                  <CardDescription>
                    Your most recently used questionnaires
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <RecentQuestionnaires />
                </CardContent>
                <CardFooter>
                  <Link href="/questionnaires">
                    <Button variant="outline">View All</Button>
                  </Link>
                </CardFooter>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Credits & Usage</CardTitle>
                <CardDescription>
                  Your available credits and recent usage
                </CardDescription>
              </CardHeader>
              <CardContent>
                <CreditSummary />
              </CardContent>
            </Card>
          </TabsContent>
          
          <TabsContent value="interviews" className="space-y-4">
            <div className="grid gap-4 grid-cols-3">
              <Link href="/interviews/new">
                <Card className="h-full cursor-pointer hover:bg-muted/50 transition-colors">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">
                      New Interview
                    </CardTitle>
                    <PlusIcon className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">Create</div>
                    <p className="text-xs text-muted-foreground pt-1">
                      Upload audio and transcribe a new interview
                    </p>
                  </CardContent>
                </Card>
              </Link>
              
              <Link href="/interviews">
                <Card className="h-full cursor-pointer hover:bg-muted/50 transition-colors">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">
                      Interviews
                    </CardTitle>
                    <FileIcon className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">Manage</div>
                    <p className="text-xs text-muted-foreground pt-1">
                      View and manage your interviews
                    </p>
                  </CardContent>
                </Card>
              </Link>
            </div>
          </TabsContent>
          
          <TabsContent value="questionnaires" className="space-y-4">
            <div className="grid gap-4 grid-cols-3">
              <Link href="/questionnaires/new">
                <Card className="h-full cursor-pointer hover:bg-muted/50 transition-colors">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">
                      New Questionnaire
                    </CardTitle>
                    <PlusIcon className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">Create</div>
                    <p className="text-xs text-muted-foreground pt-1">
                      Design a new interview questionnaire
                    </p>
                  </CardContent>
                </Card>
              </Link>
              
              <Link href="/questionnaires">
                <Card className="h-full cursor-pointer hover:bg-muted/50 transition-colors">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">
                      View All
                    </CardTitle>
                    <FileIcon className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">Questionnaires</div>
                    <p className="text-xs text-muted-foreground pt-1">
                      Browse and manage all your questionnaires
                    </p>
                  </CardContent>
                </Card>
              </Link>
            </div>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}