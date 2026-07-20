'use server'

import { prisma } from '@/lib/prisma'
import { setSession, clearSession } from '@/lib/session'
import { hash, compare } from 'bcryptjs'
import { redirect } from 'next/navigation'

export async function registerUser(prevState: any, formData: FormData) {
  const name = formData.get('name') as string
  const email = formData.get('email') as string
  const password = formData.get('password') as string
  const riskProfile = formData.get('riskProfile') as string
  const investmentGoal = formData.get('investmentGoal') as string

  if (!email || !password || !name) {
    return { error: 'Tous les champs sont requis.' }
  }

  try {
    const existingUser = await prisma.user.findUnique({ where: { email } })
    if (existingUser) {
      return { error: 'Cet email est déjà utilisé.' }
    }

    const hashedPassword = await hash(password, 10)

    const user = await prisma.user.create({
      data: { name, email, password: hashedPassword, riskProfile },
    })

    await setSession(user.id)
  } catch (error) {
    console.error("REGISTER ERROR:", error)
    return { error: 'Une erreur est survenue lors de la création du compte.' }
  }

  redirect('/dashboard')
}

export async function loginUser(prevState: any, formData: FormData) {
  const email = formData.get('email') as string
  const password = formData.get('password') as string

  if (!email || !password) {
    return { error: 'Email et mot de passe requis.' }
  }

  try {
    const user = await prisma.user.findUnique({ where: { email } })
    if (!user) {
      return { error: 'Identifiants invalides.' }
    }

    const passwordMatch = await compare(password, user.password)
    if (!passwordMatch) {
      return { error: 'Identifiants invalides.' }
    }

    await setSession(user.id)
  } catch (error) {
    return { error: 'Une erreur est survenue lors de la connexion.' }
  }

  redirect('/dashboard')
}

export async function logoutUser() {
  await clearSession()
  redirect('/login')
}

export async function checkAuthStatus() {
  const { getSession } = await import('@/lib/session')
  const session = await getSession()
  return !!session?.userId
}

export async function getUserProfile() {
  const { getSession } = await import('@/lib/session')
  const session = await getSession()
  if (!session?.userId) return null
  
  const user = await prisma.user.findUnique({
    where: { id: session.userId },
    select: { 
      name: true, email: true, riskProfile: true, 
      taxOnboarded: true, profession: true, maritalStatus: true,
      children: true, income: true, otherIncome: true, contractType: true,
      contractDuration: true, parentsProfession: true, financialAids: true, taxGoal: true 
    }
  })
  
  return user
}

export async function updateTaxProfile(data: any) {
  const { getSession } = await import('@/lib/session')
  const session = await getSession()
  if (!session?.userId) return { error: 'Non authentifié' }

  try {
    await prisma.user.update({
      where: { id: session.userId },
      data: {
        ...data,
        taxOnboarded: true
      }
    })
    return { success: true }
  } catch (error) {
    console.error("UPDATE TAX ERROR:", error)
    return { error: 'Erreur lors de la sauvegarde.' }
  }
}
