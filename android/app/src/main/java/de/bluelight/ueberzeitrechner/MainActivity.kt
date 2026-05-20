package de.bluelight.ueberzeitrechner

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import de.bluelight.ueberzeitrechner.ui.BereitschaftScreen
import de.bluelight.ueberzeitrechner.ui.CalendarScreen
import de.bluelight.ueberzeitrechner.ui.MainScreen
import de.bluelight.ueberzeitrechner.ui.SettingsScreen
import de.bluelight.ueberzeitrechner.ui.StatsScreen
import de.bluelight.ueberzeitrechner.ui.theme.UeberzeitRechnerTheme
import de.bluelight.ueberzeitrechner.viewmodel.MainViewModel

class MainActivity : ComponentActivity() {
    private val viewModel: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            UeberzeitRechnerTheme {
                val navController = rememberNavController()
                val items = listOf(
                    NavigationItem.Dashboard,
                    NavigationItem.Calendar,
                    NavigationItem.Bereitschaft,
                    NavigationItem.Stats,
                    NavigationItem.Settings
                )

                Scaffold(
                    modifier = Modifier.fillMaxSize(),
                    bottomBar = {
                        NavigationBar {
                            val navBackStackEntry by navController.currentBackStackEntryAsState()
                            val currentRoute = navBackStackEntry?.destination?.route
                            items.forEach { item ->
                                NavigationBarItem(
                                    icon = { Icon(item.icon, contentDescription = item.title) },
                                    label = { Text(item.title, maxLines = 1) },
                                    selected = currentRoute == item.route,
                                    onClick = {
                                        navController.navigate(item.route) {
                                            navController.graph.startDestinationRoute?.let { route ->
                                                popUpTo(route) {
                                                    saveState = true
                                                }
                                            }
                                            launchSingleTop = true
                                            restoreState = true
                                        }
                                    }
                                )
                            }
                        }
                    }
                ) { innerPadding ->
                    NavHost(
                        navController = navController,
                        startDestination = NavigationItem.Dashboard.route,
                        modifier = Modifier.padding(innerPadding)
                    ) {
                        composable(NavigationItem.Dashboard.route) {
                            MainScreen(viewModel)
                        }
                        composable(NavigationItem.Calendar.route) {
                            CalendarScreen(viewModel)
                        }
                        composable(NavigationItem.Bereitschaft.route) {
                            BereitschaftScreen(viewModel)
                        }
                        composable(NavigationItem.Stats.route) {
                            StatsScreen(viewModel)
                        }
                        composable(NavigationItem.Settings.route) {
                            SettingsScreen(viewModel)
                        }
                    }
                }
            }
        }
    }
}

sealed class NavigationItem(val route: String, val icon: ImageVector, val title: String) {
    object Dashboard : NavigationItem("dashboard", Icons.Default.Home, "Erfassung")
    object Calendar : NavigationItem("calendar", Icons.Default.DateRange, "Kalender")
    object Bereitschaft : NavigationItem("bereitschaft", Icons.Default.Build, "Bereitschaft")
    object Stats : NavigationItem("stats", Icons.Default.Info, "Statistik")
    object Settings : NavigationItem("settings", Icons.Default.Settings, "Setup")
}
