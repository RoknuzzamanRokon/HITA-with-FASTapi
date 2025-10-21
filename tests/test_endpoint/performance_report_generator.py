"""
Performance report generator for user management system
Generates comprehensive performance reports with visualizations and recommendations
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
import statistics

from tests.performance_monitoring import global_performance_collector, global_concurrency_monitor
from tests.benchmark_config import BenchmarkConfig, PERFORMANCE_TEST_SCENARIOS


class PerformanceReportGenerator:
    """Generate comprehensive performance reports"""
    
    def __init__(self, output_dir: str = "performance_reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.report_timestamp = datetime.now()
    
    def generate_comprehensive_report(self, test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        
        report = {
            'metadata': {
                'generated_at': self.report_timestamp.isoformat(),
                'report_version': '1.0',
                'test_duration': test_results.get('test_execution', {}).get('duration', 0)
            },
            'executive_summary': self._generate_executive_summary(test_results),
            'performance_metrics': self._analyze_performance_metrics(),
            'benchmark_analysis': self._analyze_benchmarks(),
            'cache_analysis': self._analyze_cache_performance(),
            'concurrency_analysis': self._analyze_concurrency_performance(),
            'recommendations': self._generate_recommendations(test_results),
            'detailed_metrics': self._get_detailed_metrics()
        }
        
        return report
    
    def _generate_executive_summary(self, test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate executive summary"""
        
        # Get overall performance metrics
        perf_summary = global_performance_collector.get_performance_summary()
        concurrency_stats = global_concurrency_monitor.get_concurrency_stats()
        
        # Calculate key metrics
        overview = perf_summary.get('overview', {})
        alerts = perf_summary.get('alerts', [])
        
        critical_alerts = [a for a in alerts if a.get('severity') == 'critical']
        warning_alerts = [a for a in alerts if a.get('severity') == 'warning']
        
        # Performance grade calculation
        performance_grade = self._calculate_performance_grade(overview, alerts)
        
        return {
            'performance_grade': performance_grade,
            'total_queries_executed': overview.get('total_queries', 0),
            'average_response_time': overview.get('recent_avg_time', 0),
            'cache_hit_rate': overview.get('overall_cache_hit_rate', 0),
            'error_rate': overview.get('overall_error_rate', 0),
            'max_concurrent_requests': concurrency_stats.get('max_concurrent_ever', 0),
            'critical_issues': len(critical_alerts),
            'warnings': len(warning_alerts),
            'test_status': 'PASSED' if len(critical_alerts) == 0 else 'FAILED',
            'key_findings': self._extract_key_findings(overview, alerts)
        }
    
    def _calculate_performance_grade(self, overview: Dict[str, Any], alerts: List[Dict[str, Any]]) -> str:
        """Calculate overall performance grade A-F"""
        
        score = 100
        
        # Deduct points for performance issues
        avg_time = overview.get('recent_avg_time', 0)
        if avg_time > 2.0:
            score -= 30
        elif avg_time > 1.0:
            score -= 15
        elif avg_time > 0.5:
            score -= 5
        
        # Deduct points for low cache hit rate
        cache_hit_rate = overview.get('overall_cache_hit_rate', 0)
        if cache_hit_rate < 0.5:
            score -= 25
        elif cache_hit_rate < 0.7:
            score -= 10
        
        # Deduct points for errors
        error_rate = overview.get('overall_error_rate', 0)
        if error_rate > 0.1:
            score -= 40
        elif error_rate > 0.05:
            score -= 20
        elif error_rate > 0.01:
            score -= 5
        
        # Deduct points for alerts
        critical_alerts = [a for a in alerts if a.get('severity') == 'critical']
        warning_alerts = [a for a in alerts if a.get('severity') == 'warning']
        
        score -= len(critical_alerts) * 15
        score -= len(warning_alerts) * 5
        
        # Convert score to grade
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'
    
    def _extract_key_findings(self, overview: Dict[str, Any], alerts: List[Dict[str, Any]]) -> List[str]:
        """Extract key findings from performance data"""
        
        findings = []
        
        # Response time findings
        avg_time = overview.get('recent_avg_time', 0)
        if avg_time < 0.1:
            findings.append("Excellent response times (< 100ms average)")
        elif avg_time < 0.5:
            findings.append("Good response times (< 500ms average)")
        elif avg_time < 1.0:
            findings.append("Acceptable response times (< 1s average)")
        else:
            findings.append(f"Slow response times ({avg_time:.3f}s average)")
        
        # Cache performance findings
        cache_hit_rate = overview.get('overall_cache_hit_rate', 0)
        if cache_hit_rate > 0.8:
            findings.append("Excellent cache performance (>80% hit rate)")
        elif cache_hit_rate > 0.6:
            findings.append("Good cache performance (>60% hit rate)")
        else:
            findings.append("Poor cache performance - needs optimization")
        
        # Error rate findings
        error_rate = overview.get('overall_error_rate', 0)
        if error_rate == 0:
            findings.append("No errors detected during testing")
        elif error_rate < 0.01:
            findings.append("Very low error rate (<1%)")
        else:
            findings.append(f"Elevated error rate ({error_rate:.1%})")
        
        # Alert findings
        critical_alerts = [a for a in alerts if a.get('severity') == 'critical']
        if critical_alerts:
            findings.append(f"{len(critical_alerts)} critical performance issues identified")
        
        return findings
    
    def _analyze_performance_metrics(self) -> Dict[str, Any]:
        """Analyze detailed performance metrics"""
        
        all_stats = global_performance_collector.get_query_statistics()
        
        # Find slowest queries
        slowest_queries = sorted(
            [(name, stats) for name, stats in all_stats.items()],
            key=lambda x: x[1].get('avg_time', 0),
            reverse=True
        )[:10]
        
        # Find most frequent queries
        most_frequent = sorted(
            [(name, stats) for name, stats in all_stats.items()],
            key=lambda x: x[1].get('count', 0),
            reverse=True
        )[:10]
        
        # Find queries with highest total time
        highest_total_time = sorted(
            [(name, stats) for name, stats in all_stats.items()],
            key=lambda x: x[1].get('total_time', 0),
            reverse=True
        )[:10]
        
        # Calculate performance distribution
        all_avg_times = [stats.get('avg_time', 0) for stats in all_stats.values()]
        
        performance_distribution = {}
        if all_avg_times:
            performance_distribution = {
                'min_response_time': min(all_avg_times),
                'max_response_time': max(all_avg_times),
                'median_response_time': statistics.median(all_avg_times),
                'p95_response_time': statistics.quantiles(all_avg_times, n=20)[18] if len(all_avg_times) > 20 else max(all_avg_times),
                'p99_response_time': statistics.quantiles(all_avg_times, n=100)[98] if len(all_avg_times) > 100 else max(all_avg_times)
            }
        
        return {
            'slowest_queries': [(name, stats['avg_time'], stats['count']) for name, stats in slowest_queries],
            'most_frequent_queries': [(name, stats['count'], stats['avg_time']) for name, stats in most_frequent],
            'highest_total_time_queries': [(name, stats['total_time'], stats['count']) for name, stats in highest_total_time],
            'performance_distribution': performance_distribution,
            'total_unique_queries': len(all_stats)
        }
    
    def _analyze_benchmarks(self) -> Dict[str, Any]:
        """Analyze performance against benchmarks"""
        
        benchmark_results = []
        all_stats = global_performance_collector.get_query_statistics()
        
        # Test against relevant benchmarks
        benchmark_mappings = {
            'get_users_with_pagination': 'user_pagination_small',
            'search_users': 'user_search',
            'get_user_statistics': 'user_statistics',
            'get_user_with_details': 'user_details'
        }
        
        for query_name, stats in all_stats.items():
            # Find matching benchmark
            benchmark_name = None
            for pattern, bench_name in benchmark_mappings.items():
                if pattern in query_name:
                    benchmark_name = bench_name
                    break
            
            if benchmark_name:
                try:
                    metrics = {
                        'execution_time': stats.get('avg_time', 0),
                        'cache_hit_rate': stats.get('cache_hit_rate', 0),
                        'error_rate': stats.get('error_rate', 0)
                    }
                    
                    result = BenchmarkConfig.validate_performance(benchmark_name, metrics)
                    benchmark_results.append({
                        'query_name': query_name,
                        'benchmark_name': benchmark_name,
                        'passed': result['passed'],
                        'failures': result['failures'],
                        'warnings': result['warnings']
                    })
                    
                except Exception as e:
                    benchmark_results.append({
                        'query_name': query_name,
                        'benchmark_name': benchmark_name,
                        'passed': False,
                        'failures': [f"Benchmark validation error: {e}"],
                        'warnings': []
                    })
        
        # Summary statistics
        total_benchmarks = len(benchmark_results)
        passed_benchmarks = len([r for r in benchmark_results if r['passed']])
        failed_benchmarks = total_benchmarks - passed_benchmarks
        
        return {
            'total_benchmarks_tested': total_benchmarks,
            'passed_benchmarks': passed_benchmarks,
            'failed_benchmarks': failed_benchmarks,
            'pass_rate': passed_benchmarks / total_benchmarks if total_benchmarks > 0 else 0,
            'benchmark_results': benchmark_results
        }
    
    def _analyze_cache_performance(self) -> Dict[str, Any]:
        """Analyze cache performance"""
        
        all_stats = global_performance_collector.get_query_statistics()
        
        # Find cached vs non-cached operations
        cached_operations = {}
        for query_name, stats in all_stats.items():
            cache_hit_rate = stats.get('cache_hit_rate', 0)
            if cache_hit_rate > 0:
                cached_operations[query_name] = {
                    'cache_hit_rate': cache_hit_rate,
                    'avg_time': stats.get('avg_time', 0),
                    'count': stats.get('count', 0)
                }
        
        # Calculate overall cache effectiveness
        if cached_operations:
            overall_hit_rate = statistics.mean([op['cache_hit_rate'] for op in cached_operations.values()])
            cache_enabled_queries = len(cached_operations)
        else:
            overall_hit_rate = 0
            cache_enabled_queries = 0
        
        # Find best and worst cache performers
        best_cache_performers = sorted(
            cached_operations.items(),
            key=lambda x: x[1]['cache_hit_rate'],
            reverse=True
        )[:5]
        
        worst_cache_performers = sorted(
            cached_operations.items(),
            key=lambda x: x[1]['cache_hit_rate']
        )[:5]
        
        return {
            'overall_cache_hit_rate': overall_hit_rate,
            'cache_enabled_queries': cache_enabled_queries,
            'total_queries': len(all_stats),
            'cache_adoption_rate': cache_enabled_queries / len(all_stats) if all_stats else 0,
            'best_cache_performers': [(name, data['cache_hit_rate'], data['avg_time']) for name, data in best_cache_performers],
            'worst_cache_performers': [(name, data['cache_hit_rate'], data['avg_time']) for name, data in worst_cache_performers],
            'cache_recommendations': self._generate_cache_recommendations(cached_operations)
        }
    
    def _generate_cache_recommendations(self, cached_operations: Dict[str, Any]) -> List[str]:
        """Generate cache-specific recommendations"""
        
        recommendations = []
        
        if not cached_operations:
            recommendations.append("No cached operations detected - consider implementing caching")
            return recommendations
        
        # Analyze cache hit rates
        low_hit_rate_ops = [name for name, data in cached_operations.items() if data['cache_hit_rate'] < 0.5]
        if low_hit_rate_ops:
            recommendations.append(f"Improve cache hit rates for {len(low_hit_rate_ops)} operations")
        
        # Analyze cache effectiveness
        avg_hit_rate = statistics.mean([data['cache_hit_rate'] for data in cached_operations.values()])
        if avg_hit_rate < 0.7:
            recommendations.append("Overall cache hit rate is below optimal (70%)")
            recommendations.append("Consider reviewing cache TTL settings and key patterns")
        
        return recommendations
    
    def _analyze_concurrency_performance(self) -> Dict[str, Any]:
        """Analyze concurrency performance"""
        
        concurrency_stats = global_concurrency_monitor.get_concurrency_stats()
        
        # Analyze concurrency patterns
        analysis = {
            'max_concurrent_requests': concurrency_stats.get('max_concurrent_ever', 0),
            'current_concurrent_requests': concurrency_stats.get('current_concurrent', 0),
            'total_requests_processed': concurrency_stats.get('total_requests', 0),
            'average_request_duration': concurrency_stats.get('avg_duration_recent', 0),
            'concurrency_efficiency': self._calculate_concurrency_efficiency(concurrency_stats)
        }
        
        # Generate concurrency recommendations
        recommendations = []
        
        max_concurrent = concurrency_stats.get('max_concurrent_ever', 0)
        if max_concurrent > 50:
            recommendations.append("High concurrency detected - monitor system resources")
        elif max_concurrent < 5:
            recommendations.append("Low concurrency - system may handle higher loads")
        
        avg_duration = concurrency_stats.get('avg_duration_recent', 0)
        if avg_duration > 2.0:
            recommendations.append("High average request duration under concurrency")
        
        analysis['recommendations'] = recommendations
        
        return analysis
    
    def _calculate_concurrency_efficiency(self, concurrency_stats: Dict[str, Any]) -> float:
        """Calculate concurrency efficiency score"""
        
        max_concurrent = concurrency_stats.get('max_concurrent_ever', 0)
        avg_duration = concurrency_stats.get('avg_duration_recent', 0)
        
        if max_concurrent == 0 or avg_duration == 0:
            return 0.0
        
        # Simple efficiency calculation
        # Higher concurrency with lower duration = better efficiency
        efficiency = min(max_concurrent / avg_duration, 100.0)
        
        return efficiency
    
    def _generate_recommendations(self, test_results: Dict[str, Any]) -> Dict[str, List[str]]:
        """Generate comprehensive recommendations"""
        
        recommendations = {
            'critical': [],
            'performance': [],
            'caching': [],
            'monitoring': [],
            'general': []
        }
        
        # Get performance data
        perf_summary = global_performance_collector.get_performance_summary()
        overview = perf_summary.get('overview', {})
        alerts = perf_summary.get('alerts', [])
        slow_queries = perf_summary.get('slow_queries', {})
        
        # Critical recommendations
        critical_alerts = [a for a in alerts if a.get('severity') == 'critical']
        for alert in critical_alerts:
            recommendations['critical'].append(alert.get('message', 'Critical issue detected'))
        
        # Performance recommendations
        if overview.get('recent_avg_time', 0) > 1.0:
            recommendations['performance'].append("Average response time exceeds 1 second - investigate slow queries")
        
        if slow_queries:
            recommendations['performance'].append(f"Optimize {len(slow_queries)} slow queries identified")
            for query_name in list(slow_queries.keys())[:3]:
                recommendations['performance'].append(f"  - Optimize query: {query_name}")
        
        # Caching recommendations
        cache_hit_rate = overview.get('overall_cache_hit_rate', 0)
        if cache_hit_rate < 0.7:
            recommendations['caching'].append("Improve cache hit rate (currently {:.1%})".format(cache_hit_rate))
            recommendations['caching'].append("Review cache TTL settings and invalidation strategies")
        
        # Monitoring recommendations
        recommendations['monitoring'].append("Implement continuous performance monitoring")
        recommendations['monitoring'].append("Set up alerting for performance degradation")
        recommendations['monitoring'].append("Monitor cache hit rates and query performance trends")
        
        # General recommendations
        recommendations['general'].append("Regular performance testing and benchmarking")
        recommendations['general'].append("Database query optimization and indexing review")
        recommendations['general'].append("Consider implementing query result pagination for large datasets")
        
        return recommendations
    
    def _get_detailed_metrics(self) -> Dict[str, Any]:
        """Get detailed metrics for technical analysis"""
        
        return {
            'query_statistics': global_performance_collector.get_query_statistics(),
            'performance_summary': global_performance_collector.get_performance_summary(),
            'concurrency_statistics': global_concurrency_monitor.get_concurrency_stats(),
            'alerts': global_performance_collector.get_performance_alerts()
        }
    
    def save_report(self, report: Dict[str, Any], format: str = 'json') -> Path:
        """Save report to file"""
        
        timestamp = self.report_timestamp.strftime('%Y%m%d_%H%M%S')
        
        if format.lower() == 'json':
            filename = f"performance_report_{timestamp}.json"
            filepath = self.output_dir / filename
            
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2, default=str)
        
        elif format.lower() == 'html':
            filename = f"performance_report_{timestamp}.html"
            filepath = self.output_dir / filename
            
            html_content = self._generate_html_report(report)
            with open(filepath, 'w') as f:
                f.write(html_content)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        return filepath
    
    def _generate_html_report(self, report: Dict[str, Any]) -> str:
        """Generate HTML report"""
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>User Management System - Performance Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .grade-A {{ color: green; font-weight: bold; }}
                .grade-B {{ color: blue; font-weight: bold; }}
                .grade-C {{ color: orange; font-weight: bold; }}
                .grade-D {{ color: red; font-weight: bold; }}
                .grade-F {{ color: darkred; font-weight: bold; }}
                .critical {{ color: red; }}
                .warning {{ color: orange; }}
                .success {{ color: green; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>User Management System - Performance Report</h1>
                <p>Generated: {report['metadata']['generated_at']}</p>
                <p>Test Duration: {report['metadata']['test_duration']:.2f} seconds</p>
            </div>
        """
        
        # Executive Summary
        summary = report['executive_summary']
        grade_class = f"grade-{summary['performance_grade']}"
        
        html += f"""
            <div class="section">
                <h2>Executive Summary</h2>
                <p><strong>Performance Grade:</strong> <span class="{grade_class}">{summary['performance_grade']}</span></p>
                <p><strong>Test Status:</strong> <span class="{'success' if summary['test_status'] == 'PASSED' else 'critical'}">{summary['test_status']}</span></p>
                <p><strong>Total Queries:</strong> {summary['total_queries_executed']}</p>
                <p><strong>Average Response Time:</strong> {summary['average_response_time']:.3f}s</p>
                <p><strong>Cache Hit Rate:</strong> {summary['cache_hit_rate']:.1%}</p>
                <p><strong>Error Rate:</strong> {summary['error_rate']:.1%}</p>
                <p><strong>Max Concurrent Requests:</strong> {summary['max_concurrent_requests']}</p>
                
                <h3>Key Findings</h3>
                <ul>
        """
        
        for finding in summary['key_findings']:
            html += f"<li>{finding}</li>"
        
        html += "</ul></div>"
        
        # Performance Metrics
        metrics = report['performance_metrics']
        html += f"""
            <div class="section">
                <h2>Performance Metrics</h2>
                <h3>Slowest Queries</h3>
                <table>
                    <tr><th>Query Name</th><th>Avg Time (s)</th><th>Executions</th></tr>
        """
        
        for query_name, avg_time, count in metrics['slowest_queries'][:10]:
            html += f"<tr><td>{query_name}</td><td>{avg_time:.3f}</td><td>{count}</td></tr>"
        
        html += "</table></div>"
        
        # Recommendations
        recommendations = report['recommendations']
        html += """
            <div class="section">
                <h2>Recommendations</h2>
        """
        
        for category, recs in recommendations.items():
            if recs:
                html += f"<h3>{category.title()}</h3><ul>"
                for rec in recs:
                    css_class = 'critical' if category == 'critical' else ''
                    html += f'<li class="{css_class}">{rec}</li>'
                html += "</ul>"
        
        html += "</div></body></html>"
        
        return html


def generate_performance_report(test_results: Dict[str, Any], output_dir: str = "performance_reports") -> Dict[str, Path]:
    """Generate comprehensive performance report"""
    
    generator = PerformanceReportGenerator(output_dir)
    report = generator.generate_comprehensive_report(test_results)
    
    # Save in multiple formats
    json_path = generator.save_report(report, 'json')
    html_path = generator.save_report(report, 'html')
    
    return {
        'json_report': json_path,
        'html_report': html_path,
        'report_data': report
    }